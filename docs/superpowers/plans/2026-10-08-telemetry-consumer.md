# Telemetry Consumer (RabbitMQ → TimescaleDB) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o microserviço `client/services/telemetry_consumer` que consome o exchange `linx.telemetry`, persiste eventos de forma idempotente no TimescaleDB do tenant, expõe `GET /telemetry` e `WS /ws/telemetry/{app_id}`, e remover o `tenant_app` e o encaminhamento REST `/ingest` do `client_agent`.

**Architecture:** Um microserviço FastAPI (uvicorn) por tenant. O consumer rabbitpy roda em thread dedicada (bloqueante) e delega persistência ao event loop asyncpg via `run_coroutine_threadsafe`. Leitura compartilha o mesmo pool; o WebSocket recebe broadcast direto do handler de ingestão (sem polling).

**Tech Stack:** Python 3.12, FastAPI, uvicorn, asyncpg, pydantic-settings, rabbitpy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-telemetry-consumer-design.md`

## Global Constraints

- Python `>=3.12,<4.0`.
- Formatação: black `line-length = 79`, isort `profile = "black"`.
- Cobertura de testes `>= 70%` (`pytest --cov=src --cov-fail-under=70`).
- Pacote: `telemetry_consumer` localizado em `client/services/telemetry_consumer/src`.
- `client/db/schema.sql` e `deploy/db/schema.sql` devem permanecer idênticos.
- Git: trabalhar na branch `feat/telemetry-consumer-rabbitmq`. **Nenhum push.**
- Exchange `linx.telemetry`; fila `linx.telemetry.{app_id}` bind `application.{app_id}.#`; DLQ `linx.telemetry.{app_id}.dlq`.
- Envelope: `{app_id, dev_eui, event_type, payload, rssi?, snr?, timestamp}`.
- Idempotência: `ON CONFLICT (dev_eui, time, event_type) DO NOTHING`.

## Review Focus

1. Mensagem reentregue (duplicata exata): não cria linha nova e é acked.
2. Corpo não-JSON ou sem campos obrigatórios: vai para a DLQ, é acked e o consumer continua vivo.
3. Banco indisponível durante o consumo: retry limitado, DLQ ao esgotar, sem derrubar o processo.
4. RabbitMQ indisponível no startup: serviço sobe e serve `/health`, reconecta com backoff.
5. Cliente WebSocket com `app_id` divergente: conexão rejeitada.
6. `before`/`limit` inválidos em `GET /telemetry`: valor rejeitado ou limitado, sem erro 500.

---

### Task 1: Scaffold, config e `/health`

**Files:**
- Modify: `client/services/telemetry_consumer/pyproject.toml`
- Delete: `client/services/telemetry_consumer/src/consumer.py`
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/__init__.py`
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/config.py`
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/app.py`
- Test: `client/services/telemetry_consumer/tests/__init__.py`
- Test: `client/services/telemetry_consumer/tests/test_config.py`
- Test: `client/services/telemetry_consumer/tests/test_app.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `ConsumerSettings` (pydantic-settings) com campos: `app_id: str`, `rabbit_url: str`, `rabbit_exchange: str`, `rabbit_prefetch_count: int`, `rabbit_connect_max_attempts: int`, `rabbit_connect_backoff_seconds: float`, `consumer_max_retries: int`, `consumer_retry_backoff_seconds: float`, `db_host: str`, `db_port: int`, `db_user: str`, `db_password: str`, `db_name: str`, `http_host: str`, `http_port: int`.
  - Propriedades em `ConsumerSettings`: `queue_name -> str`, `dead_letter_queue_name -> str`, `binding_key -> str`.
  - `create_app(settings: ConsumerSettings | None = None, *, pool_factory=None, consumer_factory=None) -> FastAPI` com rota `GET /health` retornando `{"status": "ok"}` nesta etapa.
  - `app = create_app()`.

- [ ] **Step 1: Reescrever `pyproject.toml`**

Dependências main: `fastapi`, `uvicorn[standard]`, `asyncpg`, `pydantic-settings`, `rabbitpy`. Dev: `pytest`, `pytest-cov`, `black`, `flake8`, `mypy`, `isort`, `taskipy`, `httpx`, `asyncpg-stubs`. Config de black/isort/mypy/taskipy espelhando `client/pyproject.toml` (`packages = [{include="telemetry_consumer", from="src"}]`, `testpaths = ["tests"]`).

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_config.py`:

```python
from telemetry_consumer.config import ConsumerSettings


def test_queue_names_for_app_id():
    settings = ConsumerSettings(app_id="app-1")
    assert settings.queue_name == "linx.telemetry.app-1"
    assert settings.dead_letter_queue_name == "linx.telemetry.app-1.dlq"
    assert settings.binding_key == "application.app-1.#"


def test_defaults():
    settings = ConsumerSettings()
    assert settings.rabbit_exchange == "linx.telemetry"
    assert settings.rabbit_prefetch_count == 10
    assert settings.consumer_max_retries == 3


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_ID", "tenant-9")
    monkeypatch.setenv("CONSUMER_MAX_RETRIES", "7")
    settings = ConsumerSettings()
    assert settings.app_id == "tenant-9"
    assert settings.consumer_max_retries == 7
```

`tests/test_app.py`:

```python
from fastapi.testclient import TestClient

from telemetry_consumer.app import create_app


def test_health():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 3: Rodar os testes e ver falhar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_config.py tests/test_app.py -v`
Expected: FAIL (`ModuleNotFoundError: telemetry_consumer`).

- [ ] **Step 4: Implementar `config.py` e `app.py`**

`config.py` com `ConsumerSettings(BaseSettings)`, `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`, defaults da spec, e as três propriedades (f-strings `linx.telemetry.{app_id}`, `...dlq`, `application.{app_id}.#`). `app.py` com `create_app` recebendo factories opcionais (guardadas para uso nas tarefas seguintes) e `@app.get("/health")` retornando `{"status": "ok"}`. Remover o stub `src/consumer.py`.

- [ ] **Step 5: Gerar lock e instalar**

Run: `poetry -C client/services/telemetry_consumer lock && poetry -C client/services/telemetry_consumer install`
Expected: lock atualizado, sem erro.

- [ ] **Step 6: Rodar os testes e ver passar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_config.py tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add client/services/telemetry_consumer/pyproject.toml client/services/telemetry_consumer/poetry.lock client/services/telemetry_consumer/src client/services/telemetry_consumer/tests
git commit -m "feat(telemetry-consumer): scaffold do serviço, config e health"
```

---

### Task 2: Esquema do banco e módulo `db`

**Files:**
- Modify: `client/db/schema.sql`
- Modify: `deploy/db/schema.sql`
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/db.py`
- Test: `client/services/telemetry_consumer/tests/test_db.py`

**Interfaces:**
- Consumes: `ConsumerSettings` (Task 1).
- Produces:
  - `async def create_db_pool(host, port, user, password, database, min_size=1, max_size=10) -> asyncpg.Pool` (registra codec JSONB).
  - `async def insert_event(pool, *, event_time: str, app_id: str, dev_eui: str, event_type: str, payload: dict, rssi: int | None, snr: float | None) -> bool` — `True` se inseriu, `False` se duplicata.
  - `async def fetch_telemetry(pool, *, dev_eui: str | None, limit: int, before: str | None) -> list[dict]`.

- [ ] **Step 1: Atualizar os dois `schema.sql`**

Aplicar exatamente o mesmo conteúdo (constraint: idênticos): adicionar colunas `app_id TEXT` e `event_type TEXT NOT NULL`, manter `create_hypertable`, e adicionar `CREATE UNIQUE INDEX IF NOT EXISTS telemetry_dedup_idx ON telemetry (dev_eui, time, event_type);`.

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_db.py` (fakes de pool/connection, sem banco real):

```python
import pytest

from telemetry_consumer import db


class FakeConnection:
    def __init__(self, status="INSERT 0 1"):
        self.status = status
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append((query, args))
        return self.status

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return [{"dev_eui": "dev1"}]


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool.connection

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_insert_event_returns_true_on_insert():
    conn = FakeConnection("INSERT 0 1")
    result = await db.insert_event(
        FakePool(conn),
        event_time="2026-10-08T12:00:00Z",
        app_id="app-1",
        dev_eui="dev1",
        event_type="up",
        payload={"temperature": 25.5},
        rssi=-70,
        snr=7.5,
    )
    assert result is True
    assert "ON CONFLICT" in conn.calls[0][0]


@pytest.mark.asyncio
async def test_insert_event_returns_false_on_conflict():
    conn = FakeConnection("INSERT 0 0")
    result = await db.insert_event(
        FakePool(conn),
        event_time="2026-10-08T12:00:00Z",
        app_id="app-1",
        dev_eui="dev1",
        event_type="up",
        payload={},
        rssi=None,
        snr=None,
    )
    assert result is False


@pytest.mark.asyncio
async def test_fetch_telemetry_filters_and_limits():
    conn = FakeConnection()
    rows = await db.fetch_telemetry(
        FakePool(conn), dev_eui="dev1", limit=50, before="2026-10-08T12:00:00Z"
    )
    assert rows == [{"dev_eui": "dev1"}]
    query = conn.calls[0][0]
    assert "LIMIT" in query
    assert "time <" in query
```

Adicionar `pytest-asyncio` às dev deps e `asyncio_mode = "auto"` em `[tool.pytest.ini_options]`.

- [ ] **Step 3: Rodar e ver falhar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_db.py -v`
Expected: FAIL (`ImportError`/`AttributeError`).

- [ ] **Step 4: Implementar `db.py`**

`create_db_pool` igual ao de `client/src/tenant/db.py`, mais `init` callback que registra `set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")`. `insert_event` executa o SQL da spec e retorna `status.endswith("0 1")`. `fetch_telemetry` monta o SELECT com `WHERE ($2::text IS NULL OR dev_eui = $2) AND ($3::timestamptz IS NULL OR time < $3::timestamptz) ORDER BY time DESC LIMIT $1`, retorna `[dict(row) for row in rows]`.

- [ ] **Step 5: Rodar e ver passar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add client/db/schema.sql deploy/db/schema.sql client/services/telemetry_consumer/pyproject.toml client/services/telemetry_consumer/poetry.lock client/services/telemetry_consumer/src/telemetry_consumer/db.py client/services/telemetry_consumer/tests/test_db.py
git commit -m "feat(telemetry-consumer): persiste envelope de forma idempotente"
```

---

### Task 3: Consumer RabbitMQ (thread, retry, DLQ)

**Files:**
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/consumer.py`
- Test: `client/services/telemetry_consumer/tests/test_consumer.py`

**Interfaces:**
- Consumes: `ConsumerSettings` (Task 1).
- Produces:
  - `class RabbitConsumer`:
    - `__init__(self, settings: ConsumerSettings, loop: asyncio.AbstractEventLoop, handler: Callable[[dict], Awaitable[bool]]) -> None`
    - `start(self) -> None` — sobe thread daemon.
    - `stop(self) -> None` — sinaliza parada e fecha conexão.
    - `health(self) -> dict` — `{rabbitmq_connected, processed, failed, last_processed_at, last_error}`.
  - `handler(envelope: dict) -> bool` retorna `True` se processou (inclui duplicata) e levanta exceção em falha transitória.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_consumer.py` (fake de queue/channel, sem broker). Cobrir: envelope válido → handler chamado e `ack`; handler que levanta em todas as tentativas → publicado na DLQ e `ack`; JSON inválido → DLQ e `ack`. Usar `RabbitConsumer.__init__` direto e um método testável `_handle_message(body: bytes)` extraído para testar sem thread:

```python
import json

from telemetry_consumer.config import ConsumerSettings
from telemetry_consumer.consumer import RabbitConsumer


class FakeMessage:
    def __init__(self, body):
        self.body = body
        self.acked = False
        self.rejected = False

    def ack(self):
        self.acked = True


class FakeChannel:
    def __init__(self):
        self.published = []

    def basic_publish(self, body, exchange, routing_key):
        self.published.append((body, exchange, routing_key))


async def _ok(envelope):
    return True


async def _always_fail(envelope):
    raise RuntimeError("db down")


def test_valid_envelope_is_acked():
    settings = ConsumerSettings(app_id="app-1", consumer_max_retries=1)
    consumer = RabbitConsumer(settings, None, _ok, channel=FakeChannel())
    message = FakeMessage(json.dumps({"app_id": "app-1"}).encode())
    consumer._handle_message(message)
    assert message.acked is True
    assert consumer.health()["processed"] == 1


def test_retry_exhausted_goes_to_dlq_and_acks():
    channel = FakeChannel()
    settings = ConsumerSettings(app_id="app-1", consumer_max_retries=2)
    consumer = RabbitConsumer(settings, None, _always_fail, channel=channel)
    message = FakeMessage(json.dumps({"app_id": "app-1"}).encode())
    consumer._handle_message(message)
    assert message.acked is True
    assert channel.published[0][2] == "linx.telemetry.app-1.dlq"
    assert consumer.health()["failed"] == 1


def test_invalid_json_goes_to_dlq_and_acks():
    channel = FakeChannel()
    settings = ConsumerSettings(app_id="app-1")
    consumer = RabbitConsumer(settings, None, _ok, channel=channel)
    message = FakeMessage(b"not-json")
    consumer._handle_message(message)
    assert message.acked is True
    assert channel.published[0][2] == "linx.telemetry.app-1.dlq"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_consumer.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementar `consumer.py`**

`RabbitConsumer` com: `channel` opcional injetável; `_open` declara exchange (topic durável), fila do tenant (durável), bind `binding_key`, DLQ (durável), `basic_qos(prefetch_count=...)`; `_run` consome com `basic_consume`/`queue.consume(no_ack=False)` chamando `_handle_message`; `_handle_message` faz `json.loads`, valida que é dict com `app_id`/`dev_eui`/`event_type`/`payload`/`timestamp`, roda o handler com retry (`consumer_max_retries`, backoff) via `asyncio.run_coroutine_threadsafe` (quando `loop` existe) e em falha publica o corpo na DLQ (`basic_publish` exchange default `""`, routing_key = nome da DLQ); sempre `ack`; atualiza estado de health. Reconexão em `_run` com backoff quando a conexão cai. `health()` devolve snapshot.

- [ ] **Step 4: Rodar e ver passar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_consumer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add client/services/telemetry_consumer/src/telemetry_consumer/consumer.py client/services/telemetry_consumer/tests/test_consumer.py
git commit -m "feat(telemetry-consumer): retry e DLQ por tenant no consumer"
```

---

### Task 4: Broadcaster e rotas de leitura (`GET /telemetry`, WebSocket)

**Files:**
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/broadcaster.py`
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/routers/__init__.py`
- Create: `client/services/telemetry_consumer/src/telemetry_consumer/routers/telemetry.py`
- Test: `client/services/telemetry_consumer/tests/test_broadcaster.py`
- Test: `client/services/telemetry_consumer/tests/test_routers.py`

**Interfaces:**
- Consumes: `ConsumerSettings` (Task 1), `db.fetch_telemetry`/`db.insert_event` (Task 2).
- Produces:
  - `class Broadcaster`: `async def register(ws) -> None`, `async def unregister(ws) -> None`, `async def broadcast(message: dict) -> None`, `count -> int`.
  - `router` (APIRouter) com `GET /telemetry` → `{"items": list[dict], "next_cursor": str | None}` e `WS /ws/telemetry/{app_id}`.
  - Lê `request.app.state` / `websocket.app.state`: `db_pool`, `broadcaster`, `settings`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_broadcaster.py`:

```python
from telemetry_consumer.broadcaster import Broadcaster


class FakeWS:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def send_json(self, message):
        if self.fail:
            raise RuntimeError("closed")
        self.sent.append(message)


async def test_broadcast_reaches_registered():
    broadcaster = Broadcaster()
    ws = FakeWS()
    await broadcaster.register(ws)
    await broadcaster.broadcast({"ok": True})
    assert ws.sent == [{"ok": True}]
    await broadcaster.unregister(ws)
    assert broadcaster.count == 0


async def test_broadcast_ignores_failed_send():
    broadcaster = Broadcaster()
    bad = FakeWS()
    bad.fail = True
    await broadcaster.register(bad)
    await broadcaster.broadcast({"ok": True})
    assert broadcaster.count == 0
```

`tests/test_routers.py` (pool fake e `TestClient`; para WS usar `client.websocket_connect`):

```python
from fastapi.testclient import TestClient

from telemetry_consumer.app import create_app
from telemetry_consumer.broadcaster import Broadcaster


class FakePool:
    def __init__(self, rows):
        self.rows = rows

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def test_get_telemetry_returns_items(monkeypatch):
    app = create_app()
    app.state.db_pool = FakePool([{"dev_eui": "dev1"}])
    client = TestClient(app)
    response = client.get("/telemetry?dev_eui=dev1&limit=10")
    assert response.status_code == 200
    assert response.json()["items"] == [{"dev_eui": "dev1"}]


def test_ws_rejects_wrong_app_id():
    app = create_app()
    app.state.broadcaster = Broadcaster()
    app.state.settings = app.state.settings or None
    client = TestClient(app)
    # app_id diferente de settings.app_id (default app-abc123)
    with client.websocket_connect("/ws/telemetry/outro-app") as ws:
        with pytest.raises(Exception):
            ws.receive_json()
```

Adicionar `import pytest` no topo do teste.

- [ ] **Step 2: Rodar e ver falhar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_broadcaster.py tests/test_routers.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementar `broadcaster.py` e `routers/telemetry.py`**

`Broadcaster` mantém um `set`; `broadcast` itera e remove conexões cujo `send_json` levanta. O router lê `db.fetch_telemetry` (limit clampado 1..1000; `next_cursor` = `items[-1]["time"]` ou `None`) e no WS valida `app_id == settings.app_id` (senão `close(code=1008)`), registra no broadcaster e faz `receive_text` em loop até `WebSocketDisconnect`.

- [ ] **Step 4: Rodar e ver passar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_broadcaster.py tests/test_routers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add client/services/telemetry_consumer/src/telemetry_consumer/broadcaster.py client/services/telemetry_consumer/src/telemetry_consumer/routers client/services/telemetry_consumer/tests/test_broadcaster.py client/services/telemetry_consumer/tests/test_routers.py
git commit -m "feat(telemetry-consumer): GET /telemetry e WebSocket"
```

---

### Task 5: Wiring do lifespan (pool + consumer + broadcaster + `/health` rico)

**Files:**
- Modify: `client/services/telemetry_consumer/src/telemetry_consumer/app.py`
- Test: `client/services/telemetry_consumer/tests/test_app.py`

**Interfaces:**
- Consumes: `ConsumerSettings` (1), `create_db_pool` (2), `RabbitConsumer` (3), `Broadcaster`/`router` (4).
- Produces: `create_app(settings=None, *, pool_factory=create_db_pool, consumer_factory=RabbitConsumer)` agora inicia pool e consumer no lifespan, registra o `router`, e `GET /health` retorna `{status, rabbitmq_connected, db_ok, processed, failed, last_processed_at, ws_connections}`.

- [ ] **Step 1: Escrever/atualizar o teste que falha**

Atualizar `tests/test_app.py` para injetar fakes e checar o health enriquecido:

```python
from fastapi.testclient import TestClient

from telemetry_consumer.app import create_app


class FakePool:
    async def close(self):
        pass


class FakeConsumer:
    def __init__(self, *args, **kwargs):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        pass

    def health(self):
        return {
            "rabbitmq_connected": True,
            "processed": 2,
            "failed": 0,
            "last_processed_at": "2026-10-08T12:00:00Z",
            "last_error": None,
        }


async def _fake_pool_factory(**kwargs):
    return FakePool()


def test_health_reports_consumer_state():
    app = create_app(pool_factory=_fake_pool_factory, consumer_factory=FakeConsumer)
    client = TestClient(app)
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["rabbitmq_connected"] is True
    assert body["processed"] == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `poetry -C client/services/telemetry_consumer run pytest tests/test_app.py -v`
Expected: FAIL (`KeyError: rabbitmq_connected`).

- [ ] **Step 3: Implementar o lifespan e o health**

No lifespan: criar `ConsumerSettings`; `pool = await pool_factory(...)` num `try/except` tolerante (log warning, `pool=None`); criar `broadcaster`; definir `handler(envelope)` async que chama `insert_event` e, em sucesso, `broadcaster.broadcast(record)`; instanciar `consumer_factory(settings, asyncio.get_running_loop(), handler)` e `start()`; guardar em `app.state` (`db_pool`, `broadcaster`, `settings`, `consumer`). No teardown: `consumer.stop()`, `pool.close()` se houver. Incluir o `router` e montar o `/health`.

- [ ] **Step 4: Rodar toda a suíte e ver passar**

Run: `poetry -C client/services/telemetry_consumer run pytest --cov=src --cov-fail-under=70 -v`
Expected: PASS, cobertura >= 70%.

- [ ] **Step 5: Commit**

```bash
git add client/services/telemetry_consumer/src/telemetry_consumer/app.py client/services/telemetry_consumer/tests/test_app.py
git commit -m "feat(telemetry-consumer): wiring do pool, consumer e health"
```

---

### Task 6: Dockerfile e compose

**Files:**
- Create: `client/services/telemetry_consumer/Dockerfile`
- Modify: `deploy/docker-compose.yml`
- Modify: `client/docker-compose.yml`

**Interfaces:**
- Consumes: comando `uvicorn telemetry_consumer.app:app` (Task 5).
- Produces: serviço `telemetry_consumer` na stack.

- [ ] **Step 1: Criar o Dockerfile**

Multi-stage baseado em `client/Dockerfile`: builder com poetry (`virtualenvs.in-project true`), runtime `python:3.12-slim`, copia `pyproject.toml`/`poetry.lock`/`src`, usuário não-root, `EXPOSE 8000`, `CMD ["uvicorn", "telemetry_consumer.app:app", "--host", "0.0.0.0", "--port", "8000"]`.

- [ ] **Step 2: Ajustar `deploy/docker-compose.yml`**

Remover o serviço `tenant_app`; remover `depends_on: tenant_app` do `client_agent`. Adicionar `telemetry_consumer` com build context `../client/services/telemetry_consumer`, `env_file: .env`, environment `APP_ID`, `RABBIT_URL` (`amqp://${RABBITMQ_DEFAULT_USER:-linx}:${RABBITMQ_DEFAULT_PASS}@rabbitmq:5672/%2f`), `DB_HOST=timescaledb`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`; `depends_on` `timescaledb` (healthy) e `rabbitmq` (healthy); sem porta publicada.

- [ ] **Step 3: Ajustar `client/docker-compose.yml`**

Substituir o serviço `tenant_app` por `telemetry_consumer` (build `.`), com `depends_on` `timescaledb` healthy e env `APP_ID`, `RABBIT_URL`, `DB_*`; manter o volume `timescaledb_data`.

- [ ] **Step 4: Validar sintaxe**

Run: `docker compose -f deploy/docker-compose.yml config -q && docker compose -f client/docker-compose.yml config -q`
Expected: sem erro (variáveis ausentes podem exigir `.env`; usar apenas para validar sintaxe).

- [ ] **Step 5: Commit**

```bash
git add client/services/telemetry_consumer/Dockerfile deploy/docker-compose.yml client/docker-compose.yml
git commit -m "build(deploy): substitui tenant_app pelo telemetry_consumer"
```

---

### Task 7: `client_agent` sem encaminhamento REST

**Files:**
- Delete: `middleware/services/client_agent/src/agent/routers/ingest.py`
- Modify: `middleware/services/client_agent/src/agent/main.py`
- Modify: `middleware/services/client_agent/src/agent/config.py`
- Modify: `middleware/services/client_agent/src/agent/routers/__init__.py`
- Modify: `middleware/services/client_agent/pyproject.toml`
- Modify: `middleware/services/client_agent/.env.example`
- Test: `middleware/services/client_agent/tests/` (remover testes de ingest, se houver)

**Interfaces:**
- Consumes: nada novo.
- Produces: `client_agent` com apenas `GetAppConfig` (gRPC) e `/health`.

- [ ] **Step 1: Remover o router e o wiring HTTP**

Apagar `routers/ingest.py`; em `main.py` remover o `http_client`, o `AsyncClient`/`httpx`, o `include_router(ingest)` e o `close` do client. Em `routers/__init__.py` remover o import de `ingest`. Em `config.py` remover `tenant_app_url` (e `ingest_timeout_seconds`, se existir). Remover `httpx` das dependências em `pyproject.toml` e `TENANT_APP_URL` do `.env.example`. Remover testes que exercitam o `/ingest` do client_agent.

- [ ] **Step 2: Rodar lint e testes do client_agent**

Run: `poetry -C middleware/services/client_agent run pytest -q && poetry -C middleware/services/client_agent run mypy src tests`
Expected: PASS, sem referência a `httpx`/`tenant_app`.

- [ ] **Step 3: Commit**

```bash
git add middleware/services/client_agent
git commit -m "refactor(client_agent): remove encaminhamento REST /ingest"
```

---

### Task 8: Remover o `tenant_app`

**Files:**
- Delete: `client/src/` (todo o pacote `tenant`)
- Delete: `client/tests/`
- Delete: `client/Dockerfile`
- Delete: `client/pyproject.toml`
- Delete: `client/poetry.lock`
- Delete: `client/htmlcov/`
- Delete: `client/services/teste/`
- Modify: `client/README.md`

**Interfaces:**
- Consumes: nada.
- Produces: diretório `client/` só com `db/`, `services/telemetry_consumer/`, `README.md`, `docker-compose.yml`.

- [ ] **Step 1: Remover com git**

```bash
git rm -r client/src client/tests client/htmlcov client/services/teste
git rm client/Dockerfile client/pyproject.toml client/poetry.lock
```

- [ ] **Step 2: Reescrever `client/README.md`**

Descrever o layout `client/services/telemetry_consumer` (ingestão AMQP + leitura REST/WS), o esquema em `client/db/schema.sql` e como subir via `client/docker-compose.yml` / `deploy/docker-compose.yml`. Remover referências a `tenant.main`, `TENANT_PORT`, `POST /ingest`.

- [ ] **Step 3: Verificar que nada fora de `client/services/telemetry_consumer` importa `tenant`**

Run: `rg -n "tenant\\.main|from tenant|import tenant|TENANT_APP_URL" client middleware linx_core --glob '!**/__pycache__/**'`
Expected: nenhuma referência ativa (referências em `docs/` são tratadas na Task 9).

- [ ] **Step 4: Commit**

```bash
git add client/README.md
git commit -m "chore(client): remove o tenant_app e limpa o layout"
```

---

### Task 9: CI do serviço

**Files:**
- Create: `.github/workflows/telemetry-consumer-ci.yml`

**Interfaces:**
- Consumes: pacote e suíte da Task 5.
- Produces: workflow com lint + testes do serviço.

- [ ] **Step 1: Criar o workflow**

Espelhar `.github/workflows/middleware-ci.yml` (um único job, sem serviço de banco), `paths: client/services/telemetry_consumer/**` e o próprio arquivo; `working-directory: client/services/telemetry_consumer`; passos: `poetry install`, `black --check src tests`, `isort --check-only src tests`, `flake8 src tests`, `mypy src tests`, `pytest --cov=src --cov-report=term-missing --cov-fail-under=70`.

- [ ] **Step 2: Validar YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/telemetry-consumer-ci.yml'))"`
Expected: sem erro.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/telemetry-consumer-ci.yml
git commit -m "ci(telemetry-consumer): lint e testes do serviço"
```

---

### Task 10: Documentação

**Files:**
- Modify: `docs/comunicacao_entre_servicos.md`
- Modify: `docs/middleware/README.md`
- Modify: `middleware/services/client_agent/README.md`
- Modify: `docs/client/README.md`
- Modify: `SPRINTS_BACKLOG.md`
- Modify: `PROGRESS.md`
- Create: `docs/telemetry-consumer/migration.md`

**Interfaces:**
- Consumes: comportamento das Tasks 1–9.
- Produces: docs alinhadas ao novo fluxo.

- [ ] **Step 1: Atualizar `docs/comunicacao_entre_servicos.md`**

Na topologia e tabelas, trocar `tenant_app` por `telemetry_consumer` (porta `8000`, FASTAPI, consome RabbitMQ e persiste/lê). Atualizar seção 5 (ingestão AMQP) e seção 7 (variáveis): remover `TENANT_APP_URL`, `CLIENT_AGENT_URL`; adicionar `APP_ID`, `RABBIT_URL`, `RABBIT_EXCHANGE`, `DB_*` do consumer. Refletir que `client_agent` só faz gRPC + `/health`.

- [ ] **Step 2: Atualizar os demais docs**

Remover o encaminhamento REST/`tenant_app` de `docs/middleware/README.md`, `middleware/services/client_agent/README.md` e `docs/client/README.md`. Em `SPRINTS_BACKLOG.md` e `PROGRESS.md`, atualizar referências ao `tenant_app` e marcar a issue #192.

- [ ] **Step 3: Criar `docs/telemetry-consumer/migration.md`**

Documentar a migração do banco (SQL de `ALTER TABLE`/dedup/índice da spec) e a ordem de deploy (aplicar migração antes de subir o consumer).

- [ ] **Step 4: Commit**

```bash
git add docs/comunicacao_entre_servicos.md docs/middleware/README.md middleware/services/client_agent/README.md docs/client/README.md SPRINTS_BACKLOG.md PROGRESS.md docs/telemetry-consumer/migration.md
git commit -m "docs: atualiza fluxo de ingestão e leitura"
```

---

## Self-Review

**Spec coverage:**
- Fila/binding/DLQ → Task 3.
- Envelope→hypertable, idempotência, schema + migração → Task 2.
- Retry/DLQ/resiliência → Task 3 (+ 5 wiring).
- `GET /telemetry`, WebSocket → Task 4.
- Config env → Task 1.
- Remoção `tenant_app` → Task 8; `client_agent` REST → Task 7.
- Dockerfile/compose → Task 6; CI → Task 9; docs → Task 10.
- `/health`, shutdown gracioso → Tasks 5.

**Step scan:** cada passo entrega um resultado verificável; sem "handle edge cases" solto; corpos de código só onde o teste não determina (SQL, parse, DLQ).

**Type consistency:** `insert_event`/`fetch_telemetry`/`Broadcaster`/`RabbitConsumer.health()` usados igualmente entre Tasks 2–5; `create_app` com `pool_factory`/`consumer_factory` consistente em 1/4/5.

**Review Focus mapping:** itens 1–2 → Task 3; item 3 → Task 3; item 4 → Task 3/5; item 5 → Task 4; item 6 → Task 4 (`limit` clamp, `before` cast).

**Proportion:** plano define interfaces e valores; corpos só para SQL/lógica não óbvia.
