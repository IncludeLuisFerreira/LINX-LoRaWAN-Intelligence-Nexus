# Tenant App Template

Molde do ambiente isolado por aplicação (motor de regras + TimescaleDB),
instanciado por aplicação no Sprint 4. Este é o scaffold inicial com
FastAPI + Poetry, entregue na issue #16. O tenant app **não** roda o
middleware: ele se comunica com o `client_agent_api` compartilhado.

## 📋 O que foi feito

- [x] Scaffold do serviço com **FastAPI** (`0.141.x`) + **Uvicorn** (`0.52.x`).
- [x] Estrutura `src/tenant/` com `main.py` (`app = FastAPI()`) e `GET /health`.
- [x] Teste de smoke (`tests/test_main.py`) validando `/health`.
- [x] Tooling de dev espelhado do `saas_backend`: `black`, `isort`, `flake8`,
      `mypy`, `pytest` + `pytest-cov`, `taskipy` e `httpx2`.
- [x] `Dockerfile` mínimo (`python:3.12-slim` + poetry + uvicorn).
- [x] Schema TimescaleDB (`db/schema.sql`) com hypertable `telemetry`
      (`time`, `dev_eui`, `payload`, `rssi`, `snr`) e índice `(dev_eui, time DESC)`.
- [x] Endpoint `POST /ingest`: valida o payload e persiste na hypertable
      `telemetry` via `asyncpg`.

## 📍 Endpoints

| Método | Rota      | Descrição                                |
| :----: | --------- | ---------------------------------------- |
| `GET`  | `/health` | Health check retornando `{"status":"ok"}` |
| `POST` | `/ingest` | Valida o payload e persiste na hypertable `telemetry`. `201` em sucesso; `422` payload inválido; `503` banco indisponível. |

## 📥 Ingestão

O `POST /ingest` recebe telemetria validada e a persiste no TimescaleDB do
tenant. Corpo esperado:

```json
{"dev_eui": "dev1", "payload": {"t": 20}, "rssi": -70, "snr": 7.5}
```

Pipeline: `Mosquitto → mqtt_consumer (client_agent_api) → POST /ingest
(client_agent_api) → POST /ingest (tenant_app) → TimescaleDB`.

## 🗄️ Banco de dados (TimescaleDB)

`db/schema.sql` cria a hypertable `telemetry`, que armazena a série temporal de
cada aplicação isolada. O schema é idempotente e é montado em
`/docker-entrypoint-initdb.d` do container TimescaleDB:

| Coluna     | Tipo        | Descrição                              |
| ---------- | ----------- | -------------------------------------- |
| `time`     | `TIMESTAMPTZ` | Timestamp da telemetria (dimensão).   |
| `dev_eui`  | `TEXT`        | Identificador do dispositivo (LoRaWAN). |
| `payload`  | `JSONB`       | Payload bruto recebido.                |
| `rssi`     | `INT`         | Indicador de intensidade do sinal.     |
| `snr`      | `FLOAT`       | Relação sinal-ruído.                   |

Índice composto `(dev_eui, time DESC)` para queries de série temporal por
dispositivo.

## 📁 Estrutura

| Arquivo                       | Responsabilidade                                |
| ----------------------------- | ----------------------------------------------- |
| `pyproject.toml`              | Dependências, pacote `tenant` e tasks de dev.   |
| `poetry.lock`                 | Versões travadas das dependências.              |
| `src/tenant/main.py`          | Aplicação FastAPI (`app`) e endpoint `/health`. |
| `tests/test_main.py`          | Smoke test do `/health` com `TestClient`.       |
| `db/schema.sql`               | Schema TimescaleDB (hypertable `telemetry`).    |
| `Dockerfile`                  | Imagem mínima para rodar o serviço.             |

## ⚙️ Instalação

```bash
poetry install
```

## ▶️ Executando

```bash
poetry run uvicorn tenant.main:app --reload
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

## 🛠️ Lint e tipos

```bash
task lint          # black + isort + mypy + flake8
```

## 🐳 Docker

```bash
docker build -t tenant-app-template .
docker run --rm -p 8000:8000 tenant-app-template
```

## 🐳 Docker Compose (ambiente tenant completo)

Sobe `timescaledb` + `tenant_app`. O tenant app **não** instancia o
`client_agent_api`: ele se comunica com o **middleware compartilhado**, cujo
endereço vem de `CLIENT_AGENT_URL`.

**Pré-requisitos:** Docker Compose V2 (`docker compose version`).

```bash
# a partir de tenant_app_template/
cp .env.example .env   # preencha as variáveis
docker compose up --build
```

Variáveis obrigatórias no `.env`:

| Variável           | Exemplo                      | Descrição                              |
| ------------------ | ---------------------------- | -------------------------------------- |
| `CLIENT_AGENT_URL` | `http://localhost:8001`      | URL base do middleware compartilhado.  |
| `APP_ID`           | `app-abc123`                 | ID da aplicação no SaaS.               |
| `MQTT_TOPIC`       | `au915_0/gateway/+/event/up` | Tópico MQTT de uplink.                 |
| `TENANT_PORT`      | `8002`                       | Porta exposta do `tenant_app`.         |
| `DB_USER`          | `tenant`                     | Usuário do PostgreSQL.                 |
| `DB_PASSWORD`      | `secret`                     | Senha do PostgreSQL.                   |
| `DB_NAME`          | `tenantdb`                   | Nome do banco.                         |
| `DB_HOST`          | `timescaledb`                | Host do TimescaleDB (em dev fora do Docker use `localhost`). |
| `DB_PORT`          | `5432`                       | Porta do TimescaleDB.                  |

> O cliente HTTP tenant→middleware ainda não está implementado (issue
> futura); aqui entra apenas a configuração/topologia.

> `depends_on: condition: service_healthy` requer Docker Compose V2. Não compatível com `docker stack deploy` (Swarm).
