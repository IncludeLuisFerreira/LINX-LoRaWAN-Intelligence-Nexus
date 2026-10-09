# Comunicação entre Serviços

> **Escopo deste documento:** como os serviços da plataforma se comunicam entre si —
> protocolos, contrato gRPC `AgentBridge`, fluxos de dados e configuração de rede. O
> contrato completo e os RPCs ainda não implementados estão descritos ao longo do
> documento.

---

## 1. Visão geral

A plataforma é um **sistema distribuído de serviços que conversam entre si**. A
orquestração é feita por um único `docker compose` (`deploy/docker-compose.yml`), que
coloca todos os serviços na mesma rede Docker e permite que se alcancem pelo **nome do
serviço** (resolução DNS interna do Compose).

Quatro protocolos sustentam a comunicação:

| Protocolo     | Uso                                                                               |
| :------------ | :-------------------------------------------------------------------------------- |
| **gRPC**      | Contrato binário `AgentBridge` — descoberta da configuração do tenant (`GetAppConfig`). |
| **HTTP/REST** | API do plano de controle (`identity_api`) e leitura de telemetria (`GET /telemetry`). |
| **MQTT**      | Ingestão de uplinks LoRaWAN publicados pelo ChirpStack (ChirpStack → `routing`).  |
| **AMQP**      | Ingestão de telemetria normalizada: exchange `topic` `linx.telemetry` do RabbitMQ → `telemetry_consumer`. |
| **WebSocket** | Leitura em tempo real de telemetria (`WS /ws/telemetry/{app_id}`).                |

### 1.1 Serviços

| Serviço (Compose) | Tecnologia            | Porta           | Papel                                                                              |
| :---------------- | :-------------------- | :-------------- | :--------------------------------------------------------------------------------- |
| `identity_api`    | FastAPI (REST)        | `8000`          | API do plano de controle: CRUD de tenants e aplicações.                            |
| `agent_bridge`    | gRPC (`grpcio`)       | `50051`         | **Servidor** do contrato `AgentBridge` — responde `GetAppConfig`.                   |
| `client_agent`    | FastAPI               | `8001`          | Middleware compartilhado: cliente gRPC (`GetAppConfig`) e `GET /health`.            |
| `routing`         | Python (paho-mqtt + rabbitpy) | —        | Ingestão: consome uplinks MQTT, valida e publica envelopes no RabbitMQ.            |
| `rabbitmq`        | RabbitMQ 3 (AMQP)     | `5672`/`15672`  | Exchange `topic` durável `linx.telemetry`; distribui telemetria aos consumidores.  |
| `telemetry_consumer` | FastAPI            | `8000`          | Ambiente isolado por aplicação: consome a fila AMQP, persiste no TimescaleDB e serve `GET /telemetry`/WebSocket. |
| `db`              | PostgreSQL 15         | `5432` (interna) | Banco do plano de controle (tenants/applications).                                 |
| `timescaledb`     | TimescaleDB (pg14)    | `5432` (interna) | Série temporal isolada do tenant (hypertable `telemetry`).                          |

### 1.2 Topologia

```mermaid
flowchart LR
    subgraph SaaS["Linx Core (plano de controle)"]
        ID["identity_api<br/>REST :8000"]
        AB["agent_bridge<br/>gRPC :50051"]
        DB[("db<br/>PostgreSQL 15")]
        ID --> DB
        AB --> DB
    end

    MQTT[["Broker MQTT<br/>:1883"]]
    RT["routing<br/>(ingest)"]
    RMQ{{"RabbitMQ<br/>exchange linx.telemetry"}}
    CA["client_agent<br/>:8001"]
    TC["telemetry_consumer<br/>:8000"]
    TS[("timescaledb")]

    MQTT -- "uplink" --> RT
    RT -- "publish (topic)" --> RMQ
    RMQ -- "entrega (fila do tenant)" --> TC
    CA -- "gRPC GetAppConfig" --> AB
    TC --> TS
    TC -. "GET /telemetry, WS" .-> FE["frontend"]
```

---

## 2. Mapa de comunicação

Resumo de **quem fala com quem**, por qual protocolo e em que momento:

| Origem                          | Destino                          | Protocolo             | Porta   | Propósito                                              | Momento       |
| :------------------------------ | :------------------------------- | :-------------------- | :------ | :----------------------------------------------------- | :------------ |
| `client_agent`                  | `agent_bridge`                   | gRPC                  | `50051` | `GetAppConfig` sob demanda (com cache) e health check  | startup / on-demand |
| Broker MQTT                     | `routing`                        | MQTT                  | `1883`  | Receber uplinks LoRaWAN do ChirpStack                  | contínuo      |
| `routing`                       | `rabbitmq` (exchange `linx.telemetry`) | AMQP            | `5672`  | Publicar envelope normalizado (routing key por tópico) | por uplink    |
| `rabbitmq` (fila do tenant)     | `telemetry_consumer`             | AMQP                  | `5672`  | Entregar envelope na fila `linx.telemetry.{app_id}`    | por evento    |
| `telemetry_consumer`            | `timescaledb`                    | PostgreSQL (`asyncpg`)| `5432`  | `INSERT` idempotente e `SELECT` na hypertable `telemetry` | por evento / leitura |
| `agent_bridge` / `identity_api` | `db`                             | PostgreSQL            | `5432`  | Ler/escrever o plano de controle                       | contínuo      |
| Frontend / clientes externos    | `telemetry_consumer`             | HTTP/REST + WebSocket | `8000`  | Histórico (`GET /telemetry`) e stream (`WS /ws/telemetry/{app_id}`) | sob demanda / contínuo |
| Frontend / clientes externos    | `identity_api`                   | HTTP/REST             | `8000`  | CRUD de tenants e aplicações                           | sob demanda   |

> **Direção do gRPC:** o contrato é único (`AgentBridge`), mas cada lado hospeda o RPC
> que lhe cabe. O **SaaS** hospeda `GetAppConfig` (em `agent_bridge`) e o `client_agent`
> é o cliente que o consome. Os demais RPCs do contrato ainda não estão implementados.

---

## 3. Contrato gRPC — `AgentBridge`

O contrato é versionado na raiz do repositório em [`proto/linx_agent.proto`](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/blob/main/proto/linx_agent.proto)
e é **compartilhado** entre o Linx Core e o Client Agent. Os stubs Python são gerados
por `scripts/gen_proto.sh` para os pacotes `linx.grpc` e `agent.grpc`.

- **Pacote:** `linx`
- **Proto:** `proto3`
- **Serviço:** `AgentBridge`

### 3.1 RPCs

| RPC               | Request          | Response    | Direção                    | Status                              |
| :---------------- | :--------------- | :---------- | :------------------------- | :---------------------------------- |
| `GetAppConfig`    | `AppId`          | `AppConfig` | Cliente → SaaS             | **Implementado e em uso**           |
| `IngestTelemetry` | `TelemetryEvent` | `Ack`       | SaaS → Cliente             | Não implementado                    |
| `SyncRule`        | `Rule`           | `Ack`       | SaaS → Cliente             | Não implementado                    |
| `ReportViolation` | `Violation`      | `Ack`       | Cliente → SaaS             | Placeholder (retorna `ok=false`)    |

### 3.2 Mensagens do fluxo de configuração

**`AppId`** — identifica a aplicação (tenant) cuja configuração se deseja.

| Campo    | Tipo   | # | Descrição                         |
| :------- | :----- | :- | :-------------------------------- |
| `app_id` | string | 1 | Identificador UUID da aplicação.  |

**`AppConfig`** — configuração devolvida pelo SaaS.

| Campo         | Tipo   | # | Descrição                                                        |
| :------------ | :----- | :- | :--------------------------------------------------------------- |
| `app_id`      | string | 1 | Identificador UUID da aplicação.                                 |
| `db_host`     | string | 2 | Host do TimescaleDB do tenant.                                   |
| `db_port`     | uint32 | 3 | Porta do TimescaleDB.                                            |
| `db_name`     | string | 4 | Nome do banco do tenant.                                         |
| `db_user`     | string | 5 | Usuário do banco.                                                |
| `db_password` | string | 6 | Senha do banco.                                                  |
| `mqtt_topic`  | string | 7 | Tópico MQTT de assinatura (`application/{app_id}/device/+/event/up`). |

**`Ack`** — confirmação genérica usada pelos demais RPCs do contrato.

| Campo   | Tipo   | # | Descrição                                   |
| :------ | :----- | :- | :------------------------------------------ |
| `ok`    | bool   | 1 | `true` se a operação foi aceita.            |
| `error` | string | 2 | Mensagem de erro (vazia em caso de sucesso). |

---

## 4. Fluxo gRPC: `GetAppConfig`

Este é o fluxo de comunicação gRPC entre o `client_agent` e o SaaS.

### 4.1 Sequência

```mermaid
sequenceDiagram
    autonumber
    participant CA as client_agent (cliente gRPC)
    participant AB as agent_bridge (SaaS, servidor gRPC)
    participant DB as db (PostgreSQL)

    Note over CA: startup (lifespan do FastAPI)
    CA->>AB: check_connectivity (channel_ready)
    Note over CA: estado exposto em GET /health
    CA->>AB: GetAppConfig(AppId{app_id}) sob demanda
    AB->>AB: valida UUID do app_id
    AB->>DB: SELECT application WHERE id = app_id
    DB-->>AB: Application
    AB-->>CA: AppConfig{app_id, db_host, db_port, db_name, db_user, db_password, mqtt_topic}
    Note over CA: cache TTL de 60 s por app_id
```

### 4.2 Quem chama

**`client_agent` (conectividade e cache).** É o único cliente gRPC restante. No startup
ele apenas valida a conectividade com o SaaS (`check_connectivity`) e expõe o resultado
em `GET /health`. Quando precisa da configuração de um tenant, resolve
`GetAppConfig(app_id)` **sob demanda**, com **cache de 60 s** (`CONFIG_CACHE_TTL_SECONDS`).

> O `telemetry_consumer` **não** usa gRPC: é um serviço por tenant, configurado por env
> (`APP_ID`, `RABBIT_URL`, `DB_*`), dono da própria fila e do pool do TimescaleDB.

### 4.3 Resolução no servidor (`agent_bridge`)

O servicer `AgentBridgeServicer.GetAppConfig`:

1. Converte `request.app_id` para `UUID` — erro de formato → `INVALID_ARGUMENT`.
2. Consulta a tabela `application` no `db` do plano de controle.
3. Monta o `AppConfig` a partir da `DATABASE_URL` configurada no `agent_bridge` (host,
   porta, nome, usuário, senha) e deriva o `mqtt_topic` como
   `application/{app_id}/device/+/event/up`.

### 4.4 Exemplo de chamada e resposta

Request (`AppId`):

```text
app_id: "206b6a58-532c-47af-a4c9-258ddb171e73"
```

Response (`AppConfig`):

```text
app_id: "206b6a58-532c-47af-a4c9-258ddb171e73"
db_host: "db"
db_port: 5432
db_name: "linx"
db_user: "linx"
db_password: "<segredo>"
mqtt_topic: "application/206b6a58-532c-47af-a4c9-258ddb171e73/device/+/event/up"
```

Log esperado no `client_agent` (`docker compose logs client_agent`):

```text
INFO agent.main Linx Core acessível em agent_bridge:50051
```

> Por segurança, `db_user`, `db_password` e `db_name` **não** são logados nem expostos.
>
> No estado atual, os campos `db_*` refletem a `DATABASE_URL` do plano de controle
> configurada no `agent_bridge`. O `client_agent` usa o `AppConfig` sob demanda com cache;
> o `telemetry_consumer` monta seu pool do TimescaleDB a partir das variáveis `DB_*`
> (não consome o `AppConfig`).

### 4.5 Tratamento de erros

| Situação                                  | Status gRPC         | Comportamento                                                  |
| :---------------------------------------- | :------------------ | :------------------------------------------------------------- |
| `app_id` não é UUID válido                | `INVALID_ARGUMENT`  | `client_agent` loga erro e segue (degradação graciosa).        |
| Aplicação não encontrada                  | `NOT_FOUND`         | Idem.                                                          |
| `db` indisponível                         | `UNAVAILABLE`       | Idem.                                                          |
| SaaS inacessível / timeout                | `UNAVAILABLE`       | `client_agent` marca `saas_grpc: false` em `/health`.          |

Em todos os casos o serviço **não** deixa de subir — a configuração vinda por env é
mantida como fallback.

### 4.6 Segurança

O canal gRPC é **inseguro** (`grpc.insecure_channel`) e o `AppConfig` trafega
`db_password` em texto plano. O endpoint `50051` do `agent_bridge` deve ser restrito no
Security Group ao IP do `client_agent` — **nunca** `0.0.0.0/0`. TLS/mTLS
entre os serviços ainda não está implementado.

---

## 5. Fluxo de ingestão de telemetria

Fecha o caminho do dado: `Mosquitto → routing (ingest) → exchange topic "linx.telemetry" → telemetry_consumer → TimescaleDB/WebSocket`.

O serviço `middleware/services/routing` consome os uplinks LoRaWAN publicados pelo
ChirpStack no broker MQTT, valida a integridade da mensagem, normaliza um envelope e
publica no exchange `topic` durável `linx.telemetry` do RabbitMQ. O middleware **não**
resolve tenant nem endpoint: a distribuição para os consumidores finais é feita por
filas e bindings no RabbitMQ.

Na partida, o `routing` declara também uma fila durável de auditoria
(`RABBIT_AUDIT_QUEUE`, default `linx.telemetry.audit`) com binding `#`, de modo que
nenhuma mensagem é descartada em silêncio enquanto não há consumidor ligado ao
exchange. Consumidores reais ligam suas próprias filas e podem usar essa fila apenas
para auditoria/reprocessamento.

O consumidor final é o `telemetry_consumer`, um serviço por tenant que declara a fila
durável `linx.telemetry.{app_id}` com binding `application.{app_id}.#`, persiste na
hypertable `telemetry` de forma idempotente e retransmite os eventos via WebSocket.

### 5.1 Sequência

```mermaid
sequenceDiagram
    autonumber
    participant MQ as Mosquitto
    participant RT as routing (ingest)
    participant RMQ as RabbitMQ (exchange linx.telemetry)
    participant CO as telemetry_consumer
    participant DB as TimescaleDB

    MQ-->>RT: application/{app_id}/device/{dev_eui}/{event_type}
    Note over RT: parse do tópico + valida JSON/object/time + cap de payload
    RT->>RT: build_envelope
    RT->>RMQ: publish routing_key=application.{app_id}.device.{dev_eui}.{event_type}
    Note over RT: publisher confirm
    RT-->>MQ: ack MQTT (manual_ack) só após o confirm
    RMQ-->>CO: entrega na fila linx.telemetry.{app_id}
    CO->>DB: INSERT ... ON CONFLICT (dev_eui, time, event_type) DO NOTHING
    CO-->>RMQ: ack (sucesso ou duplicata; DLQ + ack em falha definitiva)
    CO-->>CO: broadcast WebSocket do evento persistido
```

### 5.2 Routing key

Formato `application.{app_id}.device.{dev_eui}.{event_type}`, derivado dos segmentos
do tópico MQTT consumido.

| Segmento     | Origem                                              |
| :----------- | :-------------------------------------------------- |
| `app_id`     | 2º segmento do tópico (`application/{app_id}/...`). |
| `dev_eui`    | 4º segmento (`.../device/{dev_eui}/...`).           |
| `event_type` | 6º segmento (`.../event/{event_type}`).             |

Cada segmento é validado por uma regex restritiva (`^[A-Za-z0-9_-]+$`) para que um
`app_id`/`dev_eui` com `.` não altere a estrutura da routing key nem falsifique
bindings. Quando o corpo traz `deviceInfo.devEui`/`deviceInfo.applicationId`, eles
precisam bater com o tópico; divergência descarta a mensagem.

### 5.3 Envelope normalizado

| Campo        | Tipo          | Obrigatório | Descrição                                                    |
| :----------- | :------------ | :---------- | :----------------------------------------------------------- |
| `app_id`     | string        | sim         | Aplicação de origem, extraída do tópico.                     |
| `dev_eui`    | string        | sim         | Identificador do dispositivo LoRaWAN.                        |
| `event_type` | string        | sim         | Tipo do evento (`up`, etc.), extraído do tópico.             |
| `payload`    | objeto (JSON) | sim         | Campo `object` do uplink ChirpStack (payload decodificado).  |
| `rssi`       | inteiro       | não         | Presente quando `rxInfo[0].rssi` existe no uplink.           |
| `snr`        | número        | não         | Presente quando `rxInfo[0].snr` existe no uplink.            |
| `timestamp`  | string        | sim         | Campo `time` do uplink ChirpStack.                           |

A mensagem é publicada com `content_type: application/json` e `delivery_mode: 2`
(persistente).

### 5.4 Tratamento de erros

O `routing` **nunca** lança exceção para fora do callback MQTT: tópico fora do formato,
JSON inválido, payload não-objeto, `object`/`time` ausentes, identidade divergente ou
payload acima de `MAX_PAYLOAD_BYTES` geram `warning` e a mensagem é descartada. JSON com
`NaN`/`Infinity` é rejeitado (`parse_constant`). A conexão com o RabbitMQ é reprocessada
com backoff até `RABBIT_CONNECT_MAX_ATTEMPTS`; falha de publicação é logada sem derrubar
o consumidor.

A entrega é **at-least-once**: o ack MQTT (QoS 1, `manual_ack`) só é dado depois que o
RabbitMQ confirma a publicação. Se o broker estiver indisponível, a mensagem fica sem
ack e é reentregue; uma republicação após timeout/nack pode duplicar. Consumidores
devem ser idempotentes.

O `telemetry_consumer` garante idempotência pelo índice único `(dev_eui, time,
event_type)`. O ack AMQP só ocorre após o `INSERT`; erro transitório de banco gera
retry (`CONSUMER_MAX_RETRIES` com backoff) e, esgotado ou payload inválido, a mensagem
vai para a DLQ `linx.telemetry.{app_id}.dlq` e recebe ack.

> **Status de execução:** o pipeline está implementado em `middleware/services/routing`
> e no `client/services/telemetry_consumer`. No `deploy/docker-compose.yml` o `routing`
> sobe junto de `mosquitto` e `rabbitmq` e publica no exchange `linx.telemetry`; o
> `telemetry_consumer` sobe junto de `timescaledb` e `rabbitmq` e consome a fila do
> tenant. A ingestão REST via `POST /ingest` foi **removida**: o RabbitMQ é o único
> caminho de ingestão.

---

## 6. Fluxo REST — `identity_api`

O plano de controle expõe a API REST consumida pelo frontend e por integrações. É o
primeiro ponto de comunicação de um cliente com a plataforma.

| Método   | Rota                                                  | Descrição                            |
| :------- | :---------------------------------------------------- | :----------------------------------- |
| `GET`    | `/health`                                             | Health check (`200`).                |
| `POST`   | `/api/v1/tenant/`                                     | Cria um tenant (`201` + `id` UUID).  |
| `GET`    | `/api/v1/tenant/`                                     | Lista tenants.                       |
| `GET`    | `/api/v1/tenant/{id}`                                 | Busca tenant por `id`.               |
| `PATCH`  | `/api/v1/tenant/{id}`                                 | Atualiza tenant.                     |
| `DELETE` | `/api/v1/tenant/{id}`                                 | Remove tenant (`204`).               |
| `POST`   | `/api/v1/tenant/{id}/applications`                    | Cria application no tenant.          |
| `GET`    | `/api/v1/tenant/{id}/applications`                    | Lista applications do tenant.        |
| `GET`    | `/api/v1/tenant/{id}/applications/{app_id}`           | Busca application.                   |
| `PATCH`  | `/api/v1/tenant/{id}/applications/{app_id}`           | Atualiza application.                |
| `DELETE` | `/api/v1/tenant/{id}/applications/{app_id}`           | Remove application (`204`).          |

O `id` e o `app_id` são `UUID` v4 gerados pelo banco. O `app_id` criado aqui é o mesmo
`APP_ID` usado pelo `telemetry_consumer` (fila/binding) e pelo `client_agent` para
resolver a configuração via gRPC.

---

## 7. Variáveis de ambiente de comunicação

As variáveis que **ligam os serviços** entre si (arquivos `.env.example` de cada módulo e
`deploy/.env`):

| Variável                 | Serviço                    | Exemplo                                    | Descrição                                                        |
| :----------------------- | :------------------------- | :----------------------------------------- | :--------------------------------------------------------------- |
| `SAAS_GRPC_HOST`         | `client_agent`             | `agent_bridge:50051`                       | Endereço do servidor gRPC do SaaS.                               |
| `GRPC_PORT`              | `agent_bridge`             | `50051`                                    | Porta de bind do servidor gRPC.                                  |
| `GRPC_TIMEOUT_SECONDS`   | `client_agent`             | `5`                                        | Timeout das chamadas gRPC.                                       |
| `CONFIG_CACHE_TTL_SECONDS` | `client_agent`           | `60`                                       | TTL do cache de `GetAppConfig`.                                  |
| `MQTT_BROKER_HOST`       | `routing`                  | `mosquitto`                                | Host do broker MQTT (ChirpStack).                                |
| `MQTT_BROKER_PORT`       | `routing`                  | `1883`                                     | Porta do broker MQTT.                                            |
| `MQTT_QOS`               | `routing`                  | `1`                                        | QoS da inscrição no tópico de uplink.                            |
| `MQTT_TOPIC`             | `routing`                  | `application/+/device/+/event/up`          | Tópico MQTT de uplink.                                           |
| `RABBIT_URL`             | `routing`, `telemetry_consumer` | `amqp://linx:linx@rabbitmq:5672/%2f`  | Conexão AMQP com o RabbitMQ.                                     |
| `RABBIT_EXCHANGE`        | `routing`, `telemetry_consumer` | `linx.telemetry`                     | Exchange `topic` durável de telemetria.                          |
| `RABBIT_AUDIT_QUEUE`     | `routing`                  | `linx.telemetry.audit`                     | Fila durável com binding `#`; evita descarte silencioso.         |
| `RABBIT_CONNECT_MAX_ATTEMPTS` | `routing`, `telemetry_consumer` | `5`                                | Tentativas de conexão ao RabbitMQ.                               |
| `RABBIT_CONNECT_BACKOFF_SECONDS` | `routing`, `telemetry_consumer` | `1.0`                          | Backoff (s) entre tentativas de conexão.                         |
| `RABBIT_PREFETCH_COUNT`  | `telemetry_consumer`       | `10`                                       | Mensagens em voo no consumidor.                                  |
| `CONSUMER_MAX_RETRIES`   | `telemetry_consumer`       | `3`                                        | Retries por mensagem antes da DLQ.                               |
| `CONSUMER_RETRY_BACKOFF_SECONDS` | `telemetry_consumer` | `1.0`                                   | Backoff (s) entre retries de processamento.                      |
| `MAX_PAYLOAD_BYTES`      | `routing`                  | `65536`                                    | Tamanho máximo do payload MQTT aceito.                           |
| `APP_ID`                 | `telemetry_consumer`       | `206b6a58-...`                             | Identidade da aplicação; define fila `linx.telemetry.{app_id}` e binding `application.{app_id}.#`. |
| `DB_HOST` / `DB_PORT`    | `telemetry_consumer`       | `timescaledb` / `5432`                     | Conexão com o TimescaleDB.                                       |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `telemetry_consumer`, `timescaledb` | `tenant` / `...` / `tenantdb` | Credenciais do banco do tenant.                        |
| `HTTP_HOST` / `HTTP_PORT` | `telemetry_consumer`      | `0.0.0.0` / `8000`                         | Bind do FastAPI de leitura.                                      |
| `DATABASE_URL`           | `agent_bridge`, `identity_api` | `postgresql+psycopg://...@db:5432/linx` | Banco do plano de controle.                                      |

> Em containers, os hosts são **nomes de serviço do Compose** (`db`, `agent_bridge`,
> `telemetry_consumer`, `mosquitto`, `rabbitmq`), não `localhost`.

---

## 8. Como verificar

```bash
# 1. Subir toda a stack
cd deploy
docker compose up -d --build
docker compose ps                       # todos os serviços "Up"

# 2. Prova do gRPC: conectividade do client_agent com o SaaS
docker compose logs client_agent | grep "Linx Core acessível"

# 3. Prova do REST: criar um tenant no banco do plano de controle
curl -i -X POST localhost:8000/api/v1/tenant/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "ACME"}'
```

Verificação do pipeline MQTT → RabbitMQ → TimescaleDB (serviços `routing` e
`telemetry_consumer`):

```bash
# publica um uplink ChirpStack válido no broker MQTT
mosquitto_pub -h localhost -p 1883 \
  -t "application/1/device/dev1/event/up" \
  -m '{"object":{"temperature":25.5},"rxInfo":[{"rssi":-70,"snr":7.5}],"time":"2026-10-08T12:00:00Z"}'
# esperado: o `routing` valida e publica o envelope no exchange `linx.telemetry`;
# o `telemetry_consumer` persiste na hypertable `telemetry` e faz broadcast no WS.

# 4. Prova da leitura: histórico persistido do tenant
curl -i "localhost:8000/telemetry?limit=10"
# esperado: 200 {"items": [...], "next_cursor": ...}
```

---

## 9. RPCs do contrato ainda não implementados

Os RPCs abaixo já estão definidos no contrato `AgentBridge`, mas ainda **não** estão
implementados:

| RPC               | Objetivo                                                            |
| :---------------- | :------------------------------------------------------------------ |
| `IngestTelemetry` | Roteamento de telemetria do SaaS para o contêiner do tenant.        |
| `SyncRule`        | Replicar regras de negócio do SaaS para o motor de regras do tenant. |
| `ReportViolation` | Notificar o SaaS quando uma regra é violada no tenant.              |
