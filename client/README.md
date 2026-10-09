# Client — Telemetry Consumer

Ambiente isolado por aplicação no lado do cliente: um consumidor de
telemetria que **ingere via AMQP** e expõe **leitura REST/WebSocket** sobre
o TimescaleDB do tenant. O serviço fica em
`services/telemetry_consumer/` e substitui o antigo `tenant_app`.

O `client/` contém apenas:

| Caminho                       | Responsabilidade                                        |
| ----------------------------- | ------------------------------------------------------- |
| `services/telemetry_consumer/` | Serviço FastAPI (ingestão AMQP + leitura REST/WS).     |
| `db/schema.sql`               | Schema TimescaleDB (hypertable `telemetry`).            |
| `docker-compose.yml`          | Compose local: TimescaleDB + `telemetry_consumer`.      |
| `README.md`                   | Este documento.                                         |

A topologia completa (MySQL/Postgres, RabbitMQ, Mosquitto, routing,
`client_agent`) sobe pelo `deploy/docker-compose.yml` na raiz do repositório.

## 📥 Ingestão (AMQP)

O `telemetry_consumer` consome uma fila por tenant
(`linx.telemetry.<APP_ID>`) ligada ao exchange topic `linx.telemetry`
(binding `application.<APP_ID>.#`). Pipeline:

```
Mosquitto → routing → RabbitMQ (linx.telemetry) → telemetry_consumer → TimescaleDB
```

Cada mensagem é um envelope JSON validado; campos obrigatórios: `app_id`,
`dev_eui`, `event_type`, `payload`, `timestamp` (`rssi` e `snr` opcionais).
Mensagens válidas são persistidas e retransmitidas via WebSocket. Payload
inválido ou falha após retries vai para a DLQ (`linx.telemetry.<APP_ID>.dlq`).
Toda mensagem recebe `ack`.

## 📍 Endpoints

| Método | Rota                         | Descrição                                              |
| :----: | ---------------------------- | ------------------------------------------------------ |
| `GET`  | `/health`                    | Estado do consumidor e do banco.                       |
| `GET`  | `/telemetry`                 | Lista telemetria. Filtros `dev_eui`, `limit`, `before`; retorna `items` e `next_cursor`. |
| `WS`   | `/ws/telemetry/{app_id}`     | Stream em tempo real. Fecha com `1008` se `app_id` não bate com `APP_ID`. |

`GET /telemetry` responde `503` quando o banco está indisponível. `limit` é
limitado ao intervalo `1..1000` (default `100`).

## 🗄️ Banco de dados (TimescaleDB)

O serviço provisiona o pool `asyncpg` no startup e grava na hypertable
`telemetry` definida em `db/schema.sql`. O schema é idempotente e é montado
em `/docker-entrypoint-initdb.d` do container TimescaleDB:

| Coluna       | Tipo          | Descrição                                |
| ------------ | ------------- | ---------------------------------------- |
| `time`       | `TIMESTAMPTZ` | Timestamp da telemetria (dimensão).      |
| `dev_eui`    | `TEXT`        | Identificador do dispositivo (LoRaWAN).  |
| `payload`    | `JSONB`       | Payload bruto recebido.                  |
| `rssi`       | `INT`         | Indicador de intensidade do sinal.       |
| `snr`        | `FLOAT`       | Relação sinal-ruído.                     |
| `app_id`     | `TEXT`        | ID da aplicação no SaaS.                 |
| `event_type` | `TEXT`        | Tipo do evento.                          |

Há um índice composto `(dev_eui, time DESC)` para queries de série temporal
por dispositivo e um índice único `(dev_eui, time, event_type)` que
desduplica eventos.

## 📁 Estrutura

| Arquivo                                        | Responsabilidade                                     |
| ---------------------------------------------- | ---------------------------------------------------- |
| `services/telemetry_consumer/pyproject.toml`   | Dependências e tasks de dev (poetry).               |
| `services/telemetry_consumer/src/.../app.py`   | App FastAPI, lifespan (pool + consumer) e `/health`. |
| `services/telemetry_consumer/src/.../config.py`| `ConsumerSettings` (AMQP, DB, HTTP) via env.         |
| `services/telemetry_consumer/src/.../consumer.py` | `RabbitConsumer` com retry, DLQ e thread dedicada. |
| `services/telemetry_consumer/src/.../db.py`    | Pool `asyncpg` (`insert_event`, `fetch_telemetry`).  |
| `services/telemetry_consumer/src/.../broadcaster.py` | Fan-out WebSocket em memória.                  |
| `services/telemetry_consumer/src/.../routers/telemetry.py` | Rotas REST e WS de leitura.          |
| `services/telemetry_consumer/tests/`           | Testes unitários (app, consumer, db, router, config).|

## ⚙️ Variáveis de ambiente

| Variável                           | Default                              | Descrição                                   |
| ---------------------------------- | ------------------------------------ | ------------------------------------------- |
| `APP_ID`                           | `app-abc123`                         | ID da aplicação no SaaS (fila/binding).     |
| `RABBIT_URL`                       | `amqp://guest:guest@localhost:5672/%2f` | URL AMQP do RabbitMQ.                    |
| `RABBIT_EXCHANGE`                  | `linx.telemetry`                     | Exchange topic de telemetria.               |
| `RABBIT_PREFETCH_COUNT`            | `10`                                 | Prefetch do consumidor.                     |
| `RABBIT_CONNECT_MAX_ATTEMPTS`      | `5`                                  | Tentativas de conexão ao RabbitMQ.          |
| `RABBIT_CONNECT_BACKOFF_SECONDS`   | `1.0`                                | Backoff entre tentativas de conexão.        |
| `CONSUMER_MAX_RETRIES`             | `3`                                  | Retries por mensagem antes da DLQ.          |
| `CONSUMER_RETRY_BACKOFF_SECONDS`   | `1.0`                                | Backoff entre retries de processamento.     |
| `DB_HOST`                          | `timescaledb`                        | Host do TimescaleDB.                        |
| `DB_PORT`                          | `5432`                               | Porta do TimescaleDB.                       |
| `DB_USER`                          | `tenant`                             | Usuário do PostgreSQL.                      |
| `DB_PASSWORD`                      | `changeme`                           | Senha do PostgreSQL.                        |
| `DB_NAME`                          | `tenantdb`                           | Nome do banco.                              |
| `HTTP_HOST`                        | `0.0.0.0`                            | Host de bind do Uvicorn.                    |
| `HTTP_PORT`                        | `8000`                               | Porta HTTP do serviço.                      |

## ▶️ Executando (local)

A partir de `client/services/telemetry_consumer/`:

```bash
poetry install
poetry run uvicorn telemetry_consumer.app:app --reload
```

Atalhos do taskipy: `task run`, `task run_reload`. Verificação:

```bash
curl http://localhost:8000/health
```

Testes e lint:

```bash
task test   # task lint + pytest --cov + coverage
task lint   # black + isort + mypy + flake8
```

## 🐳 Docker Compose

### Ambiente local (`client/docker-compose.yml`)

Sobe `timescaledb` + `telemetry_consumer`. O schema é montado no container
do banco e o serviço só inicia após o healthcheck do TimescaleDB.

```bash
# a partir de client/
cp .env.example .env   # preencha as variáveis
docker compose up --build
```

Variáveis usadas no `.env`: `APP_ID`, `RABBIT_URL`, `DB_USER`,
`DB_PASSWORD`, `DB_NAME`.

### Stack completa (`deploy/docker-compose.yml`)

Na raiz do repositório, sobe a topologia de produção: `db`, `identity_api`,
`nginx`, `agent_bridge`, `client_agent`, `timescaledb`, `telemetry_consumer`,
`mosquitto`, `rabbitmq` e `routing`. O `telemetry_consumer` é construído a
partir de `../client/services/telemetry_consumer` e recebe o `RABBIT_URL`
apontando para o serviço `rabbitmq`.

```bash
# a partir de deploy/
docker compose up --build
```

> `depends_on: condition: service_healthy` requer Docker Compose V2. Não é
> compatível com `docker stack deploy` (Swarm).
