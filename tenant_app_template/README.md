# Tenant App Template

Molde do Docker Cliente do **Aluno 3** — o serviço que será instanciado por
aplicação no Sprint 4. Este é o scaffold inicial com FastAPI + Poetry,
entregue na issue #16.

## 📋 O que foi feito

- [x] Scaffold do serviço com **FastAPI** (`0.141.x`) + **Uvicorn** (`0.52.x`).
- [x] Estrutura `src/tenant/` com `main.py` (`app = FastAPI()`) e `GET /health`.
- [x] Teste de smoke (`tests/test_main.py`) validando `/health`.
- [x] Tooling de dev espelhado do `saas_backend`: `black`, `isort`, `flake8`,
      `mypy`, `pytest` + `pytest-cov`, `taskipy` e `httpx2`.
- [x] `Dockerfile` mínimo (`python:3.12-slim` + poetry + uvicorn).
- [x] Schema TimescaleDB (`db/schema.sql`) com hypertable `telemetry`
      (`time`, `dev_eui`, `payload`, `rssi`, `snr`) e índice `(dev_eui, time DESC)`.

## 📍 Endpoints

| Método | Rota      | Descrição                                |
| :----: | --------- | ---------------------------------------- |
| `GET`  | `/health` | Health check retornando `{"status":"ok"}` |

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

Sobe `timescaledb` + `client_agent` isolados por tenant.

**Pré-requisitos:** Docker Compose V2 (`docker compose version`).

```bash
# a partir de tenant_app_template/
cp .env.example .env   # preencha as variáveis
docker compose up --build
```

Variáveis obrigatórias no `.env`:

| Variável      | Exemplo         | Descrição                        |
| ------------- | --------------- | -------------------------------- |
| `APP_ID`      | `app-abc123`    | ID da aplicação no SaaS          |
| `MQTT_TOPIC`  | `au915_0/+/...` | Tópico MQTT de uplink            |
| `TENANT_PORT` | `8001`          | Porta exposta do `client_agent`  |
| `DB_USER`     | `tenant`        | Usuário do PostgreSQL            |
| `DB_PASSWORD` | `secret`        | Senha do PostgreSQL              |
| `DB_NAME`     | `tenantdb`      | Nome do banco                    |

> `depends_on: condition: service_healthy` requer Docker Compose V2. Não compatível com `docker stack deploy` (Swarm).
