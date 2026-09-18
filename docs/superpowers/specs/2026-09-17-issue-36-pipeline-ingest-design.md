# Design: pipeline Mosquitto → mqtt_consumer → POST /ingest → TimescaleDB (issue #36)

**Data:** 2026-09-17
**Issue:** [#36](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/36)
**Sprint:** 2
**Escopo:** consumer MQTT (reuso #18) → `/ingest` do middleware → `/ingest` do tenant_app → TimescaleDB
**Relacionado:** #18 (mqtt_consumer), #34 (Model A — `client_agent_api` como middleware compartilhado), #35 (`POST /ingest`), #47 (roteamento no SaaS — fora de escopo)

## Contexto

A issue #36 pede fechar o caminho do dado `Mosquitto → mqtt_consumer → POST /ingest → TimescaleDB`.
O corpo original da issue colocava consumer e `/ingest` no `client_agent_api`, mas o
design **Model A** (#34, README do `client_agent_api`) define o `client_agent_api`
como **middleware compartilhado** e o `tenant_app_template` como ambiente isolado
por aplicação (com seu próprio TimescaleDB).

Decisão acordada: o pipeline fecha na Sprint 2 com o middleware como **entrada de
ingestão** e o `tenant_app_template` como **destino final** que persiste no
TimescaleDB local. O consumer MQTT no SaaS Backend e o roteamento por
`device_routes` ficam para a #47 (Sprint 3).

> A branch local `feat/35-post-ingest-timescaledb` implementava `/ingest` no
> middleware persistindo direto no banco. Esse desenho é **superado** por este
> design (o `/ingest` de persistência passa a viver no tenant_app; o middleware
> apenas encaminha). Recomenda-se fechar/repurpar a #35.

## Objetivo

- `mosquitto_pub` em `application/1/device/dev1/event/up` resulta em linha na
  hypertable `telemetry` do TimescaleDB do tenant, sem intervenção manual.
- Payload inválido é rejeitado com `422`.
- Pipeline verificável ponta-a-ponta com `mosquitto_pub` + `SELECT`.

## Não-objetivos

- Consumer MQTT no SaaS Backend e roteamento por `app_id`/`device_routes` (#47).
- Parse do payload ChirpStack v4 (#49) e normalização do `object` (#50).
- `GET /api/v1/telemetry/{dev_eui}` (#51) e WebSocket (#52).
- Multi-tenant real: no MVP o endpoint do tenant_app é fixo via env.

## Arquitetura e fluxo

```
mosquitto_pub  (tópico application/1/device/dev1/event/up)
  └─ MqttConsumer            [client_agent_api, processo separado]
       ├─ json.loads → exige dev_eui, payload (rssi/snr opcionais)
       └─ POST {INGEST_URL}  → default http://localhost:8001/ingest   (httpx sync)
            └─ POST /ingest  [client_agent_api FastAPI, middleware]
                 ├─ valida TelemetryIn → 422
                 └─ POST {TENANT_APP_URL}/ingest → default http://localhost:8002/ingest (httpx async)
                      └─ POST /ingest  [tenant_app_template FastAPI]
                           ├─ valida TelemetryIn → 422
                           └─ INSERT INTO telemetry(...)  (asyncpg)
                                └─ TimescaleDB do tenant
```

## Componentes

### `tenant_app_template/` (destino)

- `src/tenant/config.py` (novo): `TenantSettings` (pydantic-settings) com
  `db_host` (default `timescaledb`), `db_port=5432`, `db_user`, `db_password`,
  `db_name`. `env_file=".env"`, `extra="ignore"`.
- `src/tenant/db.py` (novo): `create_db_pool(...)` e `insert_telemetry(pool,
  dev_eui, payload, rssi, snr)` com query parametrizada:
  `INSERT INTO telemetry (time, dev_eui, payload, rssi, snr) VALUES (NOW(), $1, $2::jsonb, $3, $4)`.
- `src/tenant/routers/__init__.py` e `src/tenant/routers/ingest.py` (novos):
  - `TelemetryIn(BaseModel)`: `dev_eui: str` (`min_length=1`),
    `payload: dict[str, Any]`, `rssi: int | None = None`, `snr: float | None = None`.
  - `POST /ingest` (`status_code=201`) → `insert_telemetry` → `{"ok": True}`.
- `src/tenant/main.py`: lifespan cria o pool (`app.state.db_pool`), registra o
  router, fecha o pool no shutdown; mantém `GET /health`. Se a criação do pool
  falhar, o app sobe com `db_pool=None` e `/ingest` responde `503`.
- `pyproject.toml`: adiciona `asyncpg` e `pydantic-settings` em runtime e
  `asyncpg-stubs` em dev.
- Testes: `tests/test_ingest.py` (201 com pool fake, 422 inválido, 503 sem pool).

### `client_agent_api/` (middleware, entrada de ingestão)

- `src/agent/config.py`: adiciona `tenant_app_url: str = "http://localhost:8002"`
  e `ingest_timeout_seconds: float = 5.0`.
- `src/agent/routers/__init__.py` e `src/agent/routers/ingest.py` (novos):
  - `TelemetryIn` (mesmo schema).
  - `POST /ingest` que encaminha via `app.state.http_client`
    (`httpx.AsyncClient`) para `{tenant_app_url}/ingest`, devolvendo o corpo/status
    do tenant_app em caso de sucesso.
- `src/agent/main.py`: lifespan cria o `httpx.AsyncClient`
  (`base_url=settings.tenant_app_url`, `timeout=settings.ingest_timeout_seconds`),
  expõe em `app.state.http_client`, registra o router e fecha o client no shutdown.
- `src/agent/mqtt_consumer.py`: `on_message` decodifica o payload, faz o parse
  mínimo (`dev_eui`, `payload`, `rssi?`, `snr?`) e faz `POST` em `INGEST_URL`
  (env, default `http://localhost:8001/ingest`) com `httpx.Client`; exceções são
  capturadas e logadas, sem vazar do callback.
- `pyproject.toml`: move `httpx` de `[dependency-groups].dev` para `dependencies`.
- Testes: `tests/test_ingest_router.py` (encaminha 201, propaga 422, 502 em
  erro de conexão) usando `httpx.MockTransport`; estende
  `tests/test_mqtt_consumer.py`; atualiza `tests/test_main.py` para o lifespan do
  http client.

### Documentação

- `client_agent_api/README.md`: documenta `POST /ingest` (encaminhamento), o
  consumer agora POSTando, e as envs `TENANT_APP_URL`/`INGEST_URL`.
- `tenant_app_template/README.md`: documenta `POST /ingest`, envs de DB e o
  pipeline.
- `tenant_app_template/.env.example`: adiciona `DB_HOST`/`DB_PORT` (default
  `timescaledb`/`5432`; em dev fora do Docker, `localhost`).

## Contrato e códigos de status

- Corpo: `{"dev_eui": "dev1", "payload": {"t": 20}, "rssi": -70, "snr": 7.5}`
  (`rssi`/`snr` opcionais).
- tenant_app `/ingest`: `201 {"ok": true}`; `422` payload inválido; `503` pool
  indisponível; `500` erro de insert.
- middleware `/ingest`: `201` (repassa corpo); `422` do tenant_app repassado;
  `502` em timeout, erro de conexão ou `5xx` do upstream.
- Consumer: JSON inválido ou campo obrigatório ausente → log `warning` e ignora;
  falha de `POST` → log `error` e ignora. O loop MQTT nunca quebra por isso.

## Erros

- Consumer: nunca lança para fora de `on_message`.
- Middleware: distingue erro de cliente (4xx repassado) de indisponibilidade do
  tenant_app (`502`).
- Tenant app: separa indisponibilidade de pool (`503`) de falha de escrita
  (`500`).

## Testes

- Unitários por camada, com mocks (sem DB nem broker):
  - tenant_app: 201, 422, 503.
  - middleware: encaminhamento, propagação de 422, 502.
  - consumer: parse + POST, JSON inválido, campos ausentes.
- Gate por serviço: `task lint && task test`.

## Verificação ponta-a-ponta

1. `docker compose -f ../infra/docker-compose.base.yml up -d mosquitto`
2. `cd tenant_app_template && docker compose up -d` (timescaledb + tenant_app)
3. `cd client_agent_api && uvicorn agent.main:app --port 8001` e, em outro
   terminal, `python -m agent.mqtt_consumer`
4. `mosquitto_pub -t application/1/device/dev1/event/up -m '{"dev_eui":"dev1","payload":{"t":20}}'`
5. `SELECT * FROM telemetry;` deve mostrar a linha.
6. `task lint && task test` em cada serviço.

## Decisões e riscos

- **Single-tenant no MVP:** `TENANT_APP_URL` fixo via env; roteamento por
  `app_id` fica para a #47.
- **#35 superada:** `/ingest` de persistência vai para o tenant_app; middleware
  só encaminha.
- **Consumer no middleware por ora:** reuso da #18; mover ao SaaS é a #47. A
  linha do README do `client_agent_api` que afirma que a ingestão MQTT vive no
  tenant será ajustada.
- **Portas:** middleware `8001`; tenant_app `8002` no host / `8000` no container.
- **Risco:** tenant_app inalcançável a partir do middleware em dev co-localizado;
  mitigado por `TENANT_APP_URL=http://localhost:8002` e documentação.
