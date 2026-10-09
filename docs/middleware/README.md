# Middleware

Serviços de middleware do LINX, em `middleware/services/`:

- **`routing`** — ingestão de telemetria: consome uplinks do ChirpStack via MQTT,
  valida e publica envelopes normalizados no RabbitMQ.
- **`client_agent`** (Model A) — middleware compartilhado: fica entre o
  frontend/integrações e os contêineres isolados por aplicação, validando acesso
  e roteando por `app_id`. No startup valida a conectividade gRPC com o SaaS
  Backend e resolve a configuração de cada tenant sob demanda via
  `GetAppConfig(app_id)`, com cache TTL.

## 🛰️ `services/routing` — ingestão MQTT → RabbitMQ

O `routing` consome o tópico de uplink do ChirpStack no broker MQTT (QoS 1),
valida a integridade da mensagem e publica um envelope normalizado em um exchange
`topic` durável do RabbitMQ. O serviço **não** resolve tenant nem endpoint: a
distribuição para os consumidores finais é feita por filas e bindings no
RabbitMQ.

Fluxo: `Mosquitto → routing (ingest) → exchange topic "linx.telemetry" → consumidores`.

### Routing key

`application.{app_id}.device.{dev_eui}.{event_type}`, derivado dos segmentos do
tópico MQTT consumido.

### Envelope normalizado

```json
{
  "app_id": "app1",
  "dev_eui": "devA",
  "event_type": "up",
  "payload": {"temperature": 25.5},
  "rssi": -70,
  "snr": 7.5,
  "timestamp": "2026-10-08T12:00:00Z"
}
```

`payload` vem de `object`, `timestamp` vem de `time` e `rssi`/`snr` vêm de
`rxInfo[0]` (opcionais) do uplink ChirpStack. A publicação usa
`content_type: application/json` e `delivery_mode: 2` (persistente).

### Validação e erros

São descartadas com `warning`, sem derrubar o consumidor: tópico fora do formato,
JSON inválido (inclui `NaN`/`Infinity`), payload não-objeto, `object`/`time` ausentes,
identidade do corpo divergente do tópico e payload acima de `MAX_PAYLOAD_BYTES`. A
conexão com o RabbitMQ é reprocessada com backoff até `RABBIT_CONNECT_MAX_ATTEMPTS`.

Na partida o serviço declara a fila durável `RABBIT_AUDIT_QUEUE` (default
`linx.telemetry.audit`) com binding `#`, garantindo que mensagens não são descartadas
em silêncio enquanto não há consumidor ligado ao exchange. A entrega é
**at-least-once**: o ack MQTT (QoS 1, `manual_ack`) só ocorre após o confirm do
RabbitMQ, então mensagens sem ack são reentregues e consumidores devem ser
idempotentes.

### Configuração

| Variável                         | Default                                 | Descrição                                 |
| :------------------------------- | :-------------------------------------- | :---------------------------------------- |
| `MQTT_BROKER_HOST`               | `localhost`                             | Host do broker MQTT (ChirpStack).         |
| `MQTT_BROKER_PORT`               | `1883`                                  | Porta do broker MQTT.                     |
| `MQTT_TOPIC`                     | `application/+/device/+/event/up`       | Tópico de uplink assinado.                |
| `MQTT_QOS`                       | `1`                                     | QoS da inscrição.                         |
| `RABBIT_URL`                     | `amqp://guest:guest@localhost:5672/%2f` | Conexão AMQP com o RabbitMQ.              |
| `RABBIT_EXCHANGE`                | `linx.telemetry`                        | Exchange `topic` durável de destino.      |
| `RABBIT_AUDIT_QUEUE`             | `linx.telemetry.audit`                  | Fila durável com binding `#`; evita descarte silencioso. |
| `RABBIT_CONNECT_MAX_ATTEMPTS`    | `5`                                     | Tentativas de conexão ao RabbitMQ.        |
| `RABBIT_CONNECT_BACKOFF_SECONDS` | `1.0`                                   | Backoff (s) entre tentativas.             |
| `MAX_PAYLOAD_BYTES`              | `65536`                                 | Cap de tamanho do payload MQTT.           |

> A senha na `RABBIT_URL` precisa de URL-encode quando tiver caracteres especiais
> (`@`, `:`, `/`, `?`...). Ex.: `p@ss` vira `p%40ss`.

### Estrutura

| Arquivo                     | Responsabilidade                                 |
| :-------------------------- | :----------------------------------------------- |
| `src/routing/config.py`     | `RoutingSettings` (MQTT, RabbitMQ, cap) via env. |
| `src/routing/consumer.py`   | `MqttConsumer` (paho-mqtt, valida e enfileira).  |
| `src/routing/validation.py` | Parse do tópico e validação do uplink.           |
| `src/routing/envelope.py`   | `build_envelope` e `routing_key`.                |
| `src/routing/publisher.py`  | `RabbitPublisher` (exchange topic, confirms).    |
| `src/routing/routing.py`    | `IngestService` — orquestra consumer e publisher. |

---

## Client Agent API

Middleware compartilhado do LINX (Modelo A) — fica entre o
frontend/integrações e os contêineres isolados por aplicação, validando acesso
e roteando por `app_id`. No startup valida a conectividade gRPC com o SaaS
Backend e resolve a configuração de cada tenant sob demanda via
`GetAppConfig(app_id)`, com cache TTL.

## 📋 O que foi feito

- [x] Scaffold do serviço com **FastAPI** (`0.141.x`) + **Uvicorn** (`0.52.x`).
- [x] Estrutura `src/agent/` com `main.py` (`app = FastAPI()`) e `GET /health`.
- [x] Teste de smoke (`tests/test_main.py`) validando `/health`.
- [x] Tooling de dev espelhado do `linx_core`: `black`, `isort`, `flake8`,
      `mypy`, `pytest` + `pytest-cov`, `taskipy` e `httpx`.
- [x] `Dockerfile` mínimo (`python:3.12-slim` + poetry + uvicorn).
- [x] Stubs gRPC do contrato `linx_agent.proto` em `src/agent/grpc/` (pacote `agent.grpc`).

## 📍 Endpoints

| Método | Rota      | Descrição                                                        |
| :----: | --------- | ---------------------------------------------------------------- |
| `GET`  | `/health` | Health check: `{"status":"ok","saas_grpc":true}` (503 e `degraded` quando o SaaS está inacessível). |

> A ingestão de telemetria **não** passa por REST: o `client_agent` deixa de expor
> `POST /ingest`. Ele fica com o cliente gRPC (`GetAppConfig`) e `GET /health`.
> A ingestão é feita pelo `routing` (MQTT → RabbitMQ) e persistida pelo
> `telemetry_consumer`.

## 🌐 Fluxo ponta-a-ponta com `curl`

O fluxo abaixo demonstra **criar um tenant** no SaaS REST e verificar a
conectividade gRPC do middleware. Os comandos valem para local e AWS — troque
apenas o host.

### Pré-requisitos e portas

| Serviço        | Porta   | Papel no fluxo                                           |
| -------------- | ------- | -------------------------------------------------------- |
| `identity_api` | `8000`  | SaaS REST — cria o tenant.                               |
| `client_agent` | `8001`  | Middleware — gRPC (`GetAppConfig`) e `/health`.          |
| `agent_bridge` | `50051` | gRPC do SaaS — configuração do tenant (`GetAppConfig`).  |

Suba a stack e confirme que os serviços estão de pé:

```bash
cd deploy
docker compose up -d --build
docker compose ps          # identity_api, client_agent e agent_bridge "Up"
```

### 1. Criar um tenant no SaaS (`identity_api`)

```bash
curl -i -X POST http://<saas>:8000/api/v1/tenant/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "ACME"}'
```

Resposta esperada (`201 Created`), com o `id` em UUID v4 e o header `Location`
apontando para o recurso:

```http
HTTP/1.1 201 Created
location: http://<saas>:8000/api/v1/tenant/3f1b6d3a-6c2e-4a1f-9c8b-2f0d5a7e1b44
content-type: application/json

{
  "name": "ACME",
  "description": "",
  "id": "3f1b6d3a-6c2e-4a1f-9c8b-2f0d5a7e1b44",
  "created_at": "2026-09-26T12:00:00Z",
  "updated_at": "2026-09-26T12:00:00Z"
}
```

> O `POST` exige a **barra final** (`/api/v1/tenant/`). Sem ela o FastAPI responde
> `307 Temporary Redirect`.

### 2. Conferir a conectividade gRPC do Client Agent

```bash
curl -i http://<agent>:8001/health
# esperado: 200 {"status":"ok","saas_grpc":true}
```

### Reproduzindo na AWS

Os comandos são os mesmos; mude apenas o host:

- `<saas>` e `<agent>` → IP público ou DNS das instâncias EC2 (podem ser a mesma
  máquina, com portas distintas).
- **Security Group (inbound):** libere `8000` (REST) e `8001` (`/health`). A porta
  `50051` (gRPC) **não** deve ir para `0.0.0.0/0` — restrinja ao IP do Client Agent.
- Com a borda TLS em nginx (#181), use `https://<dominio>` no lugar de
  `http://<saas>`; o encaminhamento interno para o backend permanece em HTTP.

### Erros comuns

| Resposta                   | Causa provável                                                            |
| -------------------------- | ------------------------------------------------------------------------- |
| `307` em `/api/v1/tenant`  | Falta a barra final (`/api/v1/tenant/`).                                 |
| `422 Unprocessable Entity` | Payload fora do schema (`name` ausente, tipos errados).                  |
| `503 Service Unavailable`  | gRPC do SaaS inacessível (`saas_grpc: false` em `/health`).              |
| `404 Not Found`            | `tenant_id`/`app_id` inexistente em rotas com `{id}`.                    |

> Visão completa da topologia, contrato gRPC e variáveis de ambiente:
> [Comunicação entre Serviços](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/blob/develop/docs/comunicacao_entre_servicos.md).

## 📁 Estrutura

| Arquivo                       | Responsabilidade                                |
| ----------------------------- | ----------------------------------------------- |
| `pyproject.toml`              | Dependências, pacote `agent` e tasks de dev.    |
| `poetry.lock`                 | Versões travadas das dependências.              |
| `src/agent/main.py`           | Aplicação FastAPI, lifespan gRPC e `/health`.   |
| `src/agent/config.py`         | `AgentSettings` (host gRPC, timeout, TTL do cache) via env. |
| `src/agent/grpc_client.py`    | `SaasGrpcClient` (`GetAppConfig` + cache TTL + conectividade). |
| `src/agent/grpc/`             | Stubs gRPC do contrato `linx_agent.proto`.      |
| `tests/test_main.py`          | Testes do `/health` e do lifespan com `TestClient`. |
| `tests/test_config.py`        | Testes dos defaults de `AgentSettings`.         |
| `tests/test_grpc_client.py`   | Testes do `SaasGrpcClient` (mapeamento, cache, erros). |
| `Dockerfile`                  | Imagem mínima para rodar o serviço (porta 8001). |

## ⚙️ Instalação

```bash
poetry install
```

## ▶️ Executando

```bash
cp .env.example .env
poetry run uvicorn agent.main:app --reload --port 8001
```

Verificação:

```bash
curl http://localhost:8001/health
# {"status":"ok","saas_grpc":true}
```

## 🔗 Middleware — conexão gRPC com o Linx Core

No startup o middleware abre um canal gRPC com o Linx Core e valida a
conectividade (sem derrubar o serviço em caso de falha). A configuração de
cada tenant é resolvida sob demanda com `GetAppConfig(app_id)` e cacheada.
Configuração por variáveis de ambiente:

| Variável                   | Default         | Descrição                                      |
| -------------------------- | --------------- | ---------------------------------------------- |
| `SAAS_GRPC_HOST`           | `agent_bridge:50051` | Endereço `host:porta` do gRPC do Linx Core. |
| `GRPC_TIMEOUT_SECONDS`     | `5`             | Timeout (s) das chamadas/checagem gRPC.        |
| `CONFIG_CACHE_TTL_SECONDS` | `60`            | TTL (s) do cache de `GetAppConfig` por `app_id`. |

> `SAAS_GRPC_HOST` precisa apontar para um endereço alcançável de dentro do
> container do middleware. `localhost:50051` só funciona em dev na mesma máquina;
> em container use o IP privado/DNS do SaaS ou um alias de rede Docker.

> O `/health` revalida a conectividade com um cache curto (5 s) e retorna
> `503`/`degraded` enquanto o SaaS estiver inacessível. Por isso não deve ser
> usado como probe de liveness — apenas como readiness de dependência.

## 🧪 Testes

```bash
poetry run pytest
```

## 🔌 Contrato gRPC (stubs)

O contrato `AgentBridge` é definido em `proto/linx_agent.proto` (raiz do repo).
Os stubs Python ficam em `src/agent/grpc/` (`linx_agent_pb2.py` e
`linx_agent_pb2_grpc.py`). Para verificar e regenerar:

```bash
poetry run python -c "from agent.grpc import linx_agent_pb2, linx_agent_pb2_grpc"
bash ../../../scripts/gen_proto.sh
```

## 🛠️ Lint e tipos

```bash
task lint          # black + isort + mypy + flake8
```

## 🐳 Docker

```bash
docker build -t client-agent-api .
docker run --rm -p 8001:8001 --env-file .env client-agent-api
```

Em produção use `docker compose -f docker-compose.prod.yml up -d`, com o
`SAAS_GRPC_HOST` apontando para o endereço acessível do Linx Core.
