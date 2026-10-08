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
| **HTTP/REST** | API do plano de controle (`identity_api`) e endpoint de ingestão (`POST /ingest`). |
| **MQTT**      | Ingestão de uplinks LoRaWAN publicados pelo ChirpStack (ChirpStack → `routing`).  |
| **AMQP**      | Distribuição da telemetria normalizada no exchange `topic` `linx.telemetry` do RabbitMQ. |

### 1.1 Serviços

| Serviço (Compose) | Tecnologia            | Porta           | Papel                                                                              |
| :---------------- | :-------------------- | :-------------- | :--------------------------------------------------------------------------------- |
| `identity_api`    | FastAPI (REST)        | `8000`          | API do plano de controle: CRUD de tenants e aplicações.                            |
| `agent_bridge`    | gRPC (`grpcio`)       | `50051`         | **Servidor** do contrato `AgentBridge` — responde `GetAppConfig`.                   |
| `client_agent`    | FastAPI               | `8001`          | Middleware compartilhado: API REST (`/ingest`, `/health`) e resolução de configuração de tenant. |
| `routing`         | Python (paho-mqtt + rabbitpy) | —        | Ingestão: consome uplinks MQTT, valida e publica envelopes no RabbitMQ.            |
| `rabbitmq`        | RabbitMQ 3 (AMQP)     | `5672`/`15672`  | Exchange `topic` durável `linx.telemetry`; distribui telemetria aos consumidores.  |
| `tenant_app`      | FastAPI               | `8002`          | Ambiente isolado por aplicação: busca a configuração via gRPC e persiste telemetria. |
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
    TA["tenant_app<br/>:8002"]
    TS[("timescaledb")]
    CO["Consumidores<br/>queues/bindings"]

    MQTT -- "uplink" --> RT
    RT -- "publish (topic)" --> RMQ
    RMQ -- "entrega" --> CO
    CA -- "gRPC GetAppConfig" --> AB
    TA -- "gRPC GetAppConfig" --> AB
    TA --> TS
```

---

## 2. Mapa de comunicação

Resumo de **quem fala com quem**, por qual protocolo e em que momento:

| Origem                          | Destino                          | Protocolo             | Porta   | Propósito                                              | Momento       |
| :------------------------------ | :------------------------------- | :-------------------- | :------ | :----------------------------------------------------- | :------------ |
| `tenant_app`                    | `agent_bridge`                   | gRPC                  | `50051` | `GetAppConfig(app_id)` — configuração do tenant        | startup       |
| `client_agent`                  | `agent_bridge`                   | gRPC                  | `50051` | `GetAppConfig` sob demanda (com cache) e health check  | startup / on-demand |
| Broker MQTT                     | `routing`                        | MQTT                  | `1883`  | Receber uplinks LoRaWAN do ChirpStack                  | contínuo      |
| `routing`                       | `rabbitmq` (exchange `linx.telemetry`) | AMQP            | `5672`  | Publicar envelope normalizado (routing key por tópico) | por uplink    |
| `client_agent` (`/ingest`)      | `tenant_app` (`/ingest`)         | HTTP/REST             | `8002`  | Encaminhar telemetria validada (endpoint REST avulso)  | sob demanda   |
| `tenant_app`                    | `timescaledb`                    | PostgreSQL (`asyncpg`)| `5432`  | `INSERT` na hypertable `telemetry`                     | por ingest    |
| `agent_bridge` / `identity_api` | `db`                             | PostgreSQL            | `5432`  | Ler/escrever o plano de controle                       | contínuo      |
| Frontend / clientes externos    | `identity_api`                   | HTTP/REST             | `8000`  | CRUD de tenants e aplicações                           | sob demanda   |

> **Direção do gRPC:** o contrato é único (`AgentBridge`), mas cada lado hospeda o RPC
> que lhe cabe. O **SaaS** hospeda `GetAppConfig` (em `agent_bridge`) e o **tenant** é o
> cliente que o consome. Os demais RPCs do contrato ainda não estão implementados.

---

## 3. Contrato gRPC — `AgentBridge`

O contrato é versionado na raiz do repositório em [`proto/linx_agent.proto`](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/blob/main/proto/linx_agent.proto)
e é **compartilhado** entre o Linx Core e o Client Agent. Os stubs Python são gerados
por `scripts/gen_proto.sh` para os pacotes `linx.grpc`, `agent.grpc` e `tenant.grpc`.

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

Este é o fluxo de comunicação gRPC entre o tenant e o SaaS.

### 4.1 Sequência

```mermaid
sequenceDiagram
    autonumber
    participant TA as tenant_app (cliente gRPC)
    participant AB as agent_bridge (SaaS, servidor gRPC)
    participant DB as db (PostgreSQL)

    Note over TA: startup (lifespan do FastAPI)
    TA->>AB: GetAppConfig(AppId{app_id})
    AB->>AB: valida UUID do app_id
    AB->>DB: SELECT application WHERE id = app_id
    DB-->>AB: Application
    AB-->>TA: AppConfig{app_id, db_host, db_port, db_name, db_user, db_password, mqtt_topic}
    Note over TA: logger.info("AppConfig received ...")
```

### 4.2 Quem chama

**`tenant_app` (no startup).** Ao subir, o `tenant_app` abre um canal gRPC com
o SaaS (`SAAS_GRPC_HOST`) e chama `GetAppConfig(APP_ID)`. A resposta é registrada em log
como prova de comunicação. A chamada é **bloqueante** e executada fora do event loop
(`asyncio.to_thread`). Se falhar, o serviço **não cai**: apenas registra um `warning` e
segue operando com as variáveis de ambiente (`DB_*`).

**`client_agent` (conectividade e cache).** O middleware também possui um cliente gRPC.
No startup ele apenas valida a conectividade com o SaaS (`check_connectivity`) e expõe o
resultado em `GET /health`. Quando precisa da configuração de um tenant, resolve
`GetAppConfig(app_id)` **sob demanda**, com **cache de 60 s** (`CONFIG_CACHE_TTL_SECONDS`).

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

Log esperado no `tenant_app` (`docker compose logs tenant_app`):

```text
INFO tenant.grpc_client AppConfig received app_id=206b6a58-... db_host=db db_port=5432 mqtt_topic=application/206b6a58-.../device/+/event/up
```

> Por segurança, `db_user`, `db_password` e `db_name` **não** são logados.
>
> No estado atual, os campos `db_*` refletem a `DATABASE_URL` do plano de controle
> configurada no `agent_bridge`. O `tenant_app` registra a resposta como prova de
> comunicação e continua montando seu pool do TimescaleDB a partir das variáveis
> `DB_*`; usar o `AppConfig` para isso ainda não está implementado.

### 4.5 Tratamento de erros

| Situação                                  | Status gRPC         | Comportamento                                                  |
| :---------------------------------------- | :------------------ | :------------------------------------------------------------- |
| `app_id` não é UUID válido                | `INVALID_ARGUMENT`  | `tenant_app`/`client_agent` loga erro e segue (degradação graciosa). |
| Aplicação não encontrada                  | `NOT_FOUND`         | Idem.                                                          |
| `db` indisponível                         | `UNAVAILABLE`       | Idem.                                                          |
| SaaS inacessível / timeout                | `UNAVAILABLE`       | `client_agent` marca `saas_grpc: false` em `/health`.          |

Em todos os casos o serviço **não** deixa de subir — a configuração vinda por env é
mantida como fallback.

### 4.6 Segurança

O canal gRPC é **inseguro** (`grpc.insecure_channel`) e o `AppConfig` trafega
`db_password` em texto plano. O endpoint `50051` do `agent_bridge` deve ser restrito no
Security Group ao IP do `client_agent`/`tenant_app` — **nunca** `0.0.0.0/0`. TLS/mTLS
entre os serviços ainda não está implementado.

---

## 5. Fluxo de ingestão de telemetria

Fecha o caminho do dado: `Mosquitto → routing (ingest) → exchange topic "linx.telemetry" → consumidores`.

O serviço `middleware/services/routing` consome os uplinks LoRaWAN publicados pelo
ChirpStack no broker MQTT, valida a integridade da mensagem, normaliza um envelope e
publica no exchange `topic` durável `linx.telemetry` do RabbitMQ. O middleware **não**
resolve tenant nem endpoint: a distribuição para os consumidores finais é feita por
filas e bindings no RabbitMQ.

### 5.1 Sequência

```mermaid
sequenceDiagram
    autonumber
    participant MQ as Mosquitto
    participant RT as routing (ingest)
    participant RMQ as RabbitMQ (exchange linx.telemetry)
    participant CO as Consumidor (queue/binding)

    MQ-->>RT: application/{app_id}/device/{dev_eui}/{event_type}
    Note over RT: parse do tópico + valida JSON/object/time + cap de payload
    RT->>RT: build_envelope
    RT->>RMQ: publish routing_key=application.{app_id}.device.{dev_eui}.{event_type}
    Note over RT: publisher confirm
    RMQ-->>CO: entrega pela fila ligada ao binding
```

### 5.2 Routing key

Formato `application.{app_id}.device.{dev_eui}.{event_type}`, derivado dos segmentos
do tópico MQTT consumido.

| Segmento     | Origem                                              |
| :----------- | :-------------------------------------------------- |
| `app_id`     | 2º segmento do tópico (`application/{app_id}/...`). |
| `dev_eui`    | 4º segmento (`.../device/{dev_eui}/...`).           |
| `event_type` | 6º segmento (`.../event/{event_type}`).             |

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
JSON inválido, payload não-objeto, `object`/`time` ausentes ou payload acima de
`MAX_PAYLOAD_BYTES` geram `warning` e a mensagem é descartada. A conexão com o RabbitMQ
é reprocessada com backoff até `RABBIT_CONNECT_MAX_ATTEMPTS`; falha de publicação é
logada sem derrubar o consumidor.

> **Status de execução:** o pipeline está implementado em `middleware/services/routing`
> e é exercitado com `mosquitto_pub` + um binding de teste no RabbitMQ. No
> `deploy/docker-compose.yml` o serviço `routing` sobe junto de `mosquitto` e `rabbitmq`
> e publica no exchange `linx.telemetry`. O endpoint REST `POST /ingest` do
> `client_agent` continua disponível para ingestão avulsa.

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
`APP_ID` usado pelo `tenant_app` para buscar a configuração via gRPC.

---

## 7. Variáveis de ambiente de comunicação

As variáveis que **ligam os serviços** entre si (arquivos `.env.example` de cada módulo e
`deploy/.env`):

| Variável                 | Serviço                    | Exemplo                                    | Descrição                                                        |
| :----------------------- | :------------------------- | :----------------------------------------- | :--------------------------------------------------------------- |
| `SAAS_GRPC_HOST`         | `tenant_app`, `client_agent` | `agent_bridge:50051`                     | Endereço do servidor gRPC do SaaS.                               |
| `GRPC_PORT`              | `agent_bridge`             | `50051`                                    | Porta de bind do servidor gRPC.                                  |
| `GRPC_TIMEOUT_SECONDS`   | `client_agent`, `tenant_app` | `5`                                      | Timeout das chamadas gRPC.                                       |
| `CONFIG_CACHE_TTL_SECONDS` | `client_agent`           | `60`                                       | TTL do cache de `GetAppConfig`.                                  |
| `TENANT_APP_URL`         | `client_agent`             | `http://tenant_app:8002`                   | Destino do encaminhamento REST de telemetria.                    |
| `MQTT_BROKER_HOST`       | `routing`                  | `mosquitto`                                | Host do broker MQTT (ChirpStack).                                |
| `MQTT_BROKER_PORT`       | `routing`                  | `1883`                                     | Porta do broker MQTT.                                            |
| `MQTT_QOS`               | `routing`                  | `1`                                        | QoS da inscrição no tópico de uplink.                            |
| `RABBIT_URL`             | `routing`                  | `amqp://guest:guest@rabbitmq:5672/%2f`     | Conexão AMQP com o RabbitMQ.                                     |
| `RABBIT_EXCHANGE`        | `routing`                  | `linx.telemetry`                           | Exchange `topic` durável de destino dos envelopes.               |
| `RABBIT_CONNECT_MAX_ATTEMPTS` | `routing`             | `5`                                        | Tentativas de conexão ao RabbitMQ.                               |
| `RABBIT_CONNECT_BACKOFF_SECONDS` | `routing`           | `1.0`                                      | Backoff (s) entre tentativas de conexão.                         |
| `MAX_PAYLOAD_BYTES`      | `routing`                  | `65536`                                    | Tamanho máximo do payload MQTT aceito.                           |
| `CLIENT_AGENT_URL`       | `tenant_app`               | `http://client_agent:8001`                 | Endereço do middleware compartilhado.                            |
| `APP_ID`                 | `tenant_app`               | `206b6a58-...`                             | Identidade da aplicação usada no `GetAppConfig`.                 |
| `MQTT_TOPIC`             | `routing`, `tenant_app`    | `application/+/device/+/event/up`          | Tópico MQTT de uplink.                                           |
| `DB_HOST` / `DB_PORT`    | `tenant_app`               | `timescaledb` / `5432`                     | Conexão com o TimescaleDB.                                       |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `tenant_app`, `timescaledb` | `tenant` / `...` / `tenantdb` | Credenciais do banco do tenant.                                  |
| `DATABASE_URL`           | `agent_bridge`, `identity_api` | `postgresql+psycopg://...@db:5432/linx` | Banco do plano de controle.                                      |

> Em containers, os hosts são **nomes de serviço do Compose** (`db`, `agent_bridge`,
> `tenant_app`, `mosquitto`, `rabbitmq`), não `localhost`.

---

## 8. Como verificar

```bash
# 1. Subir toda a stack
cd deploy
docker compose up -d --build
docker compose ps                       # todos os serviços "Up"

# 2. Prova do gRPC: AppConfig recebido do SaaS no startup do tenant_app
docker compose logs tenant_app | grep "AppConfig received"

# 3. Prova do REST: criar um tenant no banco do plano de controle
curl -i -X POST localhost:8000/api/v1/tenant/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "ACME"}'

# 4. Prova da ingestão: persistir telemetria no TimescaleDB do tenant
curl -i -X POST localhost:8001/ingest \
  -H 'Content-Type: application/json' \
  -d '{"dev_eui": "dev1", "payload": {"temperature": 25.5}, "rssi": -70, "snr": 7.5}'
# esperado: 201 {"ok": true}
```

Verificação do pipeline MQTT → RabbitMQ (serviço `routing`):

```bash
# publica um uplink ChirpStack válido no broker MQTT
mosquitto_pub -h localhost -p 1883 \
  -t "application/1/device/dev1/event/up" \
  -m '{"object":{"temperature":25.5},"rxInfo":[{"rssi":-70,"snr":7.5}],"time":"2026-10-08T12:00:00Z"}'
# esperado: o `routing` valida e publica o envelope no exchange `linx.telemetry`
# (confirme pela management UI em :15672 ou por um binding de teste no RabbitMQ)
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
