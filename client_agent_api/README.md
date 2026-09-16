# Client Agent API

Gateway/middleware compartilhado do LINX (Modelo A) — fica entre o
frontend/integrações e os contêineres isolados por aplicação, validando acesso
e roteando por `app_id`. No startup valida a conectividade gRPC com o SaaS
Backend e resolve a configuração de cada tenant sob demanda via
`GetAppConfig(app_id)`, com cache TTL.

> A ingestão MQTT do tenant vive no `tenant_app_template`, não neste gateway.

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

## 🔗 Gateway gRPC (SaaS Backend)

No startup o gateway abre um canal gRPC com o SaaS Backend e valida a
conectividade (sem derrubar o serviço em caso de falha). A configuração de
cada tenant é resolvida sob demanda com `GetAppConfig(app_id)` e cacheada.
Configuração por variáveis de ambiente:

| Variável                   | Default         | Descrição                                      |
| -------------------------- | --------------- | ---------------------------------------------- |
| `SAAS_GRPC_HOST`           | `saas:50051`    | Endereço `host:porta` do gRPC do SaaS Backend. |
| `GRPC_TIMEOUT_SECONDS`     | `5`             | Timeout (s) das chamadas/checagem gRPC.        |
| `CONFIG_CACHE_TTL_SECONDS` | `60`            | TTL (s) do cache de `GetAppConfig` por `app_id`. |

## 🧪 Testes

```bash
poetry run pytest
```

## 📡 Consumidor MQTT

O `MqttConsumer` assina o tópico `application/+/device/+/event/up` no Mosquitto
e loga o payload de cada uplink recebido. Configuração por variáveis de
ambiente:

| Variável            | Default                              | Descrição                    |
| ------------------- | ------------------------------------ | ---------------------------- |
| `MQTT_BROKER_HOST`  | `localhost`                          | Host do broker MQTT.         |
| `MQTT_BROKER_PORT`  | `1883`                               | Porta do broker MQTT.        |
| `MQTT_TOPIC`        | `application/+/device/+/event/up`    | Tópico de assinatura.        |

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
