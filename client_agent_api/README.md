# Client Agent API

Middleware de segurança/roteamento do **Aluno 3** — um dos dois módulos do
tenant implantado por aplicação (Sprint 4). Este é o scaffold inicial com
FastAPI + Poetry, entregue na issue #16.

## 📋 O que foi feito

- [x] Scaffold do serviço com **FastAPI** (`0.141.x`) + **Uvicorn** (`0.52.x`).
- [x] Estrutura `src/agent/` com `main.py` (`app = FastAPI()`) e `GET /health`.
- [x] Teste de smoke (`tests/test_main.py`) validando `/health`.
- [x] Tooling de dev espelhado do `saas_backend`: `black`, `isort`, `flake8`,
      `mypy`, `pytest` + `pytest-cov`, `taskipy` e `httpx2`.
- [x] `Dockerfile` mínimo (`python:3.12-slim` + poetry + uvicorn).
- [x] Consumidor MQTT (`src/agent/mqtt_consumer.py`) que assina
      `application/+/device/+/event/up` e loga o payload de cada uplink.
- [x] Stubs gRPC do contrato `saas_agent.proto` em `src/agent/grpc/` (pacote `agent.grpc`).

## 📍 Endpoints

| Método | Rota      | Descrição                                |
| :----: | --------- | ---------------------------------------- |
| `GET`  | `/health` | Health check retornando `{"status":"ok"}` |

## 📁 Estrutura

| Arquivo                       | Responsabilidade                                |
| ----------------------------- | ----------------------------------------------- |
| `pyproject.toml`              | Dependências, pacote `agent` e tasks de dev.    |
| `poetry.lock`                 | Versões travadas das dependências.              |
| `src/agent/main.py`           | Aplicação FastAPI (`app`) e endpoint `/health`. |
| `src/agent/mqtt_consumer.py`  | Consumidor MQTT de uplinks (`MqttConsumer`).    |
| `src/agent/grpc/`             | Stubs gRPC do contrato `saas_agent.proto`.      |
| `tests/test_main.py`          | Smoke test do `/health` com `TestClient`.       |
| `tests/test_mqtt_consumer.py` | Testes do consumidor com `paho-mqtt` mockado.   |
| `Dockerfile`                  | Imagem mínima para rodar o serviço.             |

## ⚙️ Instalação

```bash
poetry install
```

## ▶️ Executando

```bash
poetry run uvicorn agent.main:app --reload
```

Verificação:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

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
docker run --rm -p 8000:8000 client-agent-api
```
