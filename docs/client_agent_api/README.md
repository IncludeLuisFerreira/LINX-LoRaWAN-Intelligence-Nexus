# Client Agent API

Middleware compartilhado do LINX (Modelo A) — fica entre o
frontend/integrações e os contêineres isolados por aplicação, validando acesso
e roteando por `app_id`. No startup valida a conectividade gRPC com o SaaS
Backend e resolve a configuração de cada tenant sob demanda via
`GetAppConfig(app_id)`, com cache TTL.

> Nesta sprint o consumer MQTT roda neste middleware e a persistência da
> telemetria vive no `tenant_app_template` (Model A). Mover o consumer ao SaaS
> Backend é a #47.

## 📋 O que foi feito

- [x] Scaffold do serviço com **FastAPI** (`0.141.x`) + **Uvicorn** (`0.52.x`).
- [x] Estrutura `src/agent/` com `main.py` (`app = FastAPI()`) e `GET /health`.
- [x] Teste de smoke (`tests/test_main.py`) validando `/health`.
- [x] Tooling de dev espelhado do `saas_backend`: `black`, `isort`, `flake8`,
      `mypy`, `pytest` + `pytest-cov`, `taskipy` e `httpx`.
- [x] `Dockerfile` mínimo (`python:3.12-slim` + poetry + uvicorn).
- [x] Consumidor MQTT (`src/agent/mqtt_consumer.py`) que assina
      `application/+/device/+/event/up` e loga o payload de cada uplink.
- [x] Stubs gRPC do contrato `saas_agent.proto` em `src/agent/grpc/` (pacote `agent.grpc`).

## 📍 Endpoints

| Método | Rota      | Descrição                                                        |
| :----: | --------- | ---------------------------------------------------------------- |
| `GET`  | `/health` | Health check: `{"status":"ok","saas_grpc":true}` (503 e `degraded` quando o SaaS está inacessível). |
| `POST` | `/ingest` | Recebe telemetria validada e encaminha ao `/ingest` do tenant app. `201` em sucesso; `422` payload inválido; `502` tenant app inacessível. |

## 🌐 Fluxo ponta-a-ponta com `curl`

Dois fluxos demonstram a Sprint 2: **criar um tenant** no SaaS REST e **ingestar
telemetria** pelo Client Agent. Os comandos valem para local e AWS — troque apenas
o host.

### Pré-requisitos e portas

| Serviço        | Porta   | Papel no fluxo                                           |
| -------------- | ------- | -------------------------------------------------------- |
| `identity_api` | `8000`  | SaaS REST — cria o tenant.                               |
| `client_agent` | `8001`  | Middleware — recebe a telemetria em `/ingest`.           |
| `tenant_app`   | `8002`  | Ambiente isolado — persiste a telemetria no TimescaleDB. |
| `agent_bridge` | `50051` | gRPC do SaaS — configuração do tenant (`GetAppConfig`).  |

Suba a stack e confirme que os serviços estão de pé:

```bash
cd deploy
docker compose up -d --build
docker compose ps          # identity_api, client_agent, tenant_app e agent_bridge "Up"
```

> A ingestão só responde `201` com o `tenant_app` no ar e o gRPC do SaaS
> (`agent_bridge`) resolvível; caso contrário, veja Erros comuns.

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

### 2. Ingestar telemetria no Client Agent

```bash
curl -i -X POST http://<agent>:8001/ingest \
  -H 'Content-Type: application/json' \
  -d '{"dev_eui": "dev1", "payload": {"temperature": 25.5}, "rssi": -50, "snr": 9.5}'
```

Resposta esperada (`201 Created`):

```http
HTTP/1.1 201 Created
content-type: application/json

{"ok": true}
```

O middleware valida o schema e encaminha para o `POST /ingest` do `tenant_app`
(`TENANT_APP_URL`, default `http://localhost:8002`), que grava na hypertable
`telemetry` do TimescaleDB. `rssi` e `snr` são opcionais.

### Reproduzindo na AWS

Os comandos são os mesmos; mude apenas o host:

- `<saas>` e `<agent>` → IP público ou DNS das instâncias EC2 (podem ser a mesma
  máquina, com portas distintas).
- **Security Group (inbound):** libere `8000` (REST) e `8001` (ingest). A porta
  `50051` (gRPC) **não** deve ir para `0.0.0.0/0` — restrinja ao IP do Client Agent.
- Com a borda TLS em nginx (#181), use `https://<dominio>` no lugar de
  `http://<saas>`; o encaminhamento interno para o backend permanece em HTTP.

### Erros comuns

| Resposta                   | Causa provável                                                            |
| -------------------------- | ------------------------------------------------------------------------- |
| `307` em `/api/v1/tenant`  | Falta a barra final (`/api/v1/tenant/`).                                 |
| `422 Unprocessable Entity` | Payload fora do schema (`name` ausente, tipos errados, `dev_eui` vazio). |
| `502 Bad Gateway`          | `tenant_app` inacessível ao `client_agent` (`TENANT_APP_URL`).           |
| `503 Service Unavailable`  | gRPC do SaaS inacessível ou pool do TimescaleDB indisponível.            |
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
| `src/agent/mqtt_consumer.py`  | Consumidor MQTT de uplinks (`MqttConsumer`).    |
| `src/agent/grpc/`             | Stubs gRPC do contrato `saas_agent.proto`.      |
| `tests/test_main.py`          | Testes do `/health` e do lifespan com `TestClient`. |
| `tests/test_config.py`        | Testes dos defaults de `AgentSettings`.         |
| `tests/test_grpc_client.py`   | Testes do `SaasGrpcClient` (mapeamento, cache, erros). |
| `tests/test_mqtt_consumer.py` | Testes do consumidor com `paho-mqtt` mockado.   |
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

## 🔗 Middleware — conexão gRPC com o SaaS Backend

No startup o middleware abre um canal gRPC com o SaaS Backend e valida a
conectividade (sem derrubar o serviço em caso de falha). A configuração de
cada tenant é resolvida sob demanda com `GetAppConfig(app_id)` e cacheada.
Configuração por variáveis de ambiente:

| Variável                   | Default         | Descrição                                      |
| -------------------------- | --------------- | ---------------------------------------------- |
| `SAAS_GRPC_HOST`           | `agent_bridge:50051` | Endereço `host:porta` do gRPC do SaaS Backend. |
| `GRPC_TIMEOUT_SECONDS`     | `5`             | Timeout (s) das chamadas/checagem gRPC.        |
| `CONFIG_CACHE_TTL_SECONDS` | `60`            | TTL (s) do cache de `GetAppConfig` por `app_id`. |
| `TENANT_APP_URL`           | `http://localhost:8002` | URL base do tenant app (destino da ingestão).  |
| `INGEST_TIMEOUT_SECONDS`   | `5`             | Timeout (s) do encaminhamento ao tenant app.    |

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

## 📡 Consumidor MQTT

O `MqttConsumer` assina o tópico `application/+/device/+/event/up` no Mosquitto,
faz o parse mínimo (`dev_eui`, `payload`, e opcionalmente `rssi`/`snr`) e faz
`POST` no `/ingest` do middleware, que encaminha ao tenant app. Configuração por
variáveis de ambiente:

| Variável            | Default                              | Descrição                    |
| ------------------- | ------------------------------------ | ---------------------------- |
| `MQTT_BROKER_HOST`  | `localhost`                          | Host do broker MQTT.         |
| `MQTT_BROKER_PORT`  | `1883`                               | Porta do broker MQTT.        |
| `MQTT_TOPIC`        | `application/+/device/+/event/up`    | Tópico de assinatura.        |
| `INGEST_URL`        | `http://localhost:8001/ingest`       | Destino do POST de ingestão. |

Subir o broker local (Mosquitto):

```bash
docker compose -f ../infra/docker-compose.base.yml up -d mosquitto
```

Executar o consumidor:

```bash
poetry run python -m agent.mqtt_consumer
```

Publicar um uplink de teste:

```bash
mosquitto_pub -h localhost -p 1883 \
  -t "application/1/device/abc123/event/up" \
  -m '{"temperature": 25.5}'
```

Saída esperada no log do consumidor:

```
Conectado ao broker MQTT localhost:1883
Inscrito no tópico application/+/device/+/event/up
Uplink recebido no tópico application/1/device/abc123/event/up: b'{"temperature": 25.5}'
```

## 🔌 Contrato gRPC (stubs)

O contrato `AgentBridge` é definido em `proto/saas_agent.proto` (raiz do repo).
Os stubs Python ficam em `src/agent/grpc/` (`saas_agent_pb2.py` e
`saas_agent_pb2_grpc.py`). Para verificar e regenerar:

```bash
poetry run python -c "from agent.grpc import saas_agent_pb2, saas_agent_pb2_grpc"
bash ../scripts/gen_proto.sh
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
`SAAS_GRPC_HOST` apontando para o endereço acessível do SaaS Backend.
