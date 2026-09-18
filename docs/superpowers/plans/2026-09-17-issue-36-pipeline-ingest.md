# Pipeline Mosquitto → mqtt_consumer → POST /ingest → TimescaleDB (issue #36) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ATENÇÃO (instrução da sessão):** NÃO execute os passos de **Commit** até o
> usuário autorizar explicitamente. Todos os demais passos podem ser executados.

**Goal:** Fechar o caminho `Mosquitto → mqtt_consumer → POST /ingest → TimescaleDB`, com o `client_agent_api` como entrada de ingestão (encaminha) e o `tenant_app_template` como destino que persiste no TimescaleDB do tenant.

**Architecture:** O `MqttConsumer` (já existente no `client_agent_api`, issue #18) faz o parse mínimo do uplink e faz `POST` no `/ingest` do middleware. O middleware valida o schema e encaminha via `httpx.AsyncClient` para o `/ingest` do `tenant_app_template`, que valida e insere na hypertable `telemetry` via `asyncpg`. O consumer no SaaS Backend e o roteamento por `device_routes` ficam para a #47.

**Tech Stack:** Python 3.12, FastAPI, pydantic, pydantic-settings, httpx, asyncpg, paho-mqtt, pytest, black, isort, mypy, flake8, taskipy.

**Spec:** `docs/superpowers/specs/2026-09-17-issue-36-pipeline-ingest-design.md`

**Fora de escopo:** consumer MQTT no SaaS Backend e roteamento por `app_id` (#47), parse ChirpStack v4 (#49), normalização (#50), `GET /telemetry` (#51), WebSocket (#52), multi-tenant real.

> **Nota:** a branch local `feat/35-post-ingest-timescaledb` fica superada por
> este plano (o `/ingest` de persistência passa a viver no tenant_app). Não
> reutilizar aquela branch; basear em `develop`.

---

## File Structure

**`tenant_app_template/` (destino)**
- Create: `src/tenant/config.py` — `TenantSettings` (DB via env).
- Create: `src/tenant/db.py` — pool asyncpg + `insert_telemetry`.
- Create: `src/tenant/routers/__init__.py` — pacote de routers.
- Create: `src/tenant/routers/ingest.py` — `TelemetryIn` + `POST /ingest`.
- Modify: `src/tenant/main.py` — lifespan do pool + registro do router.
- Modify: `pyproject.toml` — deps `asyncpg`, `pydantic-settings`, `asyncpg-stubs`.
- Create: `tests/test_ingest.py`.

**`client_agent_api/` (middleware)**
- Modify: `src/agent/config.py` — `tenant_app_url`, `ingest_timeout_seconds`.
- Create: `src/agent/routers/__init__.py`.
- Create: `src/agent/routers/ingest.py` — `TelemetryIn` + `POST /ingest` (forward).
- Modify: `src/agent/main.py` — lifespan do `httpx.AsyncClient` + router.
- Modify: `src/agent/mqtt_consumer.py` — parse + POST.
- Modify: `pyproject.toml` — `httpx` para runtime.
- Create: `tests/test_ingest_router.py`.
- Modify: `tests/test_main.py`.
- Modify: `tests/test_mqtt_consumer.py`.

**Docs**
- Modify: `client_agent_api/README.md`.
- Modify: `tenant_app_template/README.md`.
- Modify: `tenant_app_template/.env.example`.

---

## Task 1: Branch de trabalho

**Files:** nenhum (git).

- [ ] **Step 1: Criar a branch a partir de `develop`**

```bash
git switch develop
git switch -c feat/36-pipeline-ingest
```

- [ ] **Step 2: Confirmar baseline verde do middleware**

Run: `cd client_agent_api && poetry run pytest -q`
Expected: PASS (testes atuais do middleware).

- [ ] **Step 3: Confirmar baseline verde do tenant**

Run: `cd tenant_app_template && poetry run pytest -q`
Expected: PASS (`test_read_health`).

---

## Task 2: tenant_app — `POST /ingest` com persistência no TimescaleDB

**Files:**
- Modify: `tenant_app_template/pyproject.toml`
- Create: `tenant_app_template/src/tenant/config.py`
- Create: `tenant_app_template/src/tenant/db.py`
- Create: `tenant_app_template/src/tenant/routers/__init__.py`
- Create: `tenant_app_template/src/tenant/routers/ingest.py`
- Modify: `tenant_app_template/src/tenant/main.py`
- Test: `tenant_app_template/tests/test_ingest.py`

- [ ] **Step 1: Adicionar dependências**

Em `tenant_app_template/pyproject.toml`, adicione `asyncpg` e `pydantic-settings`
ao bloco `dependencies` (após `"uvicorn[standard] ..."`):

```toml
dependencies = [
    "fastapi (>=0.141.1,<0.142.0)",
    "uvicorn[standard] (>=0.52.4,<0.53.0)",
    "asyncpg (>=0.31.0,<0.32.0)",
    "pydantic-settings (>=2.15.0,<3.0.0)"
]
```

E `asyncpg-stubs` ao bloco `[dependency-groups].dev` (após `"httpx2 ..."`):

```toml
    "httpx2 (>=2.12.0,<3.0.0)",
    "asyncpg-stubs (>=0.31.3,<0.32.0)"
```

- [ ] **Step 2: Instalar dependências**

Run: `cd tenant_app_template && poetry lock && poetry install`
Expected: lock atualizado e instalação sem erro.

- [ ] **Step 3: Escrever os testes que falham**

Crie `tenant_app_template/tests/test_ingest.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from tenant.main import app

client = TestClient(app)


@pytest.fixture
def fake_pool():
    connection = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=connection)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = acquire_cm
    app.state.db_pool = pool
    yield pool, connection
    del app.state.db_pool


def test_ingest_persists_and_returns_201(fake_pool):
    pool, connection = fake_pool

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True}
    connection.execute.assert_awaited_once()
    args = connection.execute.await_args.args
    assert "INSERT INTO telemetry" in args[0]
    assert args[1] == "dev1"
    assert args[2] == '{"t": 20}'


def test_ingest_invalid_payload_returns_422():
    response = client.post("/ingest", json={"payload": {"t": 20}})
    assert response.status_code == 422


def test_ingest_without_pool_returns_503():
    if hasattr(app.state, "db_pool"):
        del app.state.db_pool

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 503
```

- [ ] **Step 4: Rodar os testes e verificar que falham**

Run: `cd tenant_app_template && poetry run pytest tests/test_ingest.py -v`
Expected: FAIL (`404`/import error, pois `/ingest` ainda não existe).

- [ ] **Step 5: Criar `src/tenant/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class TenantSettings(BaseSettings):
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "tenant"
    db_password: str = "changeme"
    db_name: str = "tenantdb"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
```

- [ ] **Step 6: Criar `src/tenant/db.py`**

```python
"""Camada de persistencia assincrona no TimescaleDB via asyncpg."""

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def create_db_pool(
    host: str = "timescaledb",
    port: int = 5432,
    user: str = "tenant",
    password: str = "changeme",
    database: str = "tenantdb",
    min_size: int = 1,
    max_size: int = 10,
) -> asyncpg.Pool:
    """Cria e retorna um pool de conexoes asyncpg."""
    return await asyncpg.create_pool(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        min_size=min_size,
        max_size=max_size,
    )


async def insert_telemetry(
    pool: asyncpg.Pool,
    dev_eui: str,
    payload: dict[str, Any],
    rssi: int | None = None,
    snr: float | None = None,
) -> None:
    """Insere registro na hypertable telemetry via query parametrizada."""
    query = """
        INSERT INTO telemetry (time, dev_eui, payload, rssi, snr)
        VALUES (NOW(), $1, $2::jsonb, $3, $4)
    """
    async with pool.acquire() as connection:
        await connection.execute(
            query,
            dev_eui,
            json.dumps(payload),
            rssi,
            snr,
        )
    logger.info("Telemetria persistida para dev_eui=%s", dev_eui)
```

- [ ] **Step 7: Criar `src/tenant/routers/__init__.py`**

Arquivo vazio (marca o pacote):

```python
```

- [ ] **Step 8: Criar `src/tenant/routers/ingest.py`**

```python
"""Router para ingestao de telemetria de dispositivos LoRaWAN."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from tenant.db import insert_telemetry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class TelemetryIn(BaseModel):
    """Schema de validacao para payload de telemetria."""

    dev_eui: str = Field(..., min_length=1)
    payload: dict[str, Any]
    rssi: int | None = None
    snr: float | None = None


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    data: TelemetryIn,
    request: Request,
) -> dict[str, bool]:
    """Valida o payload e persiste na hypertable do TimescaleDB."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.error("Pool de conexoes do banco nao inicializado")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool unavailable",
        )

    try:
        await insert_telemetry(
            pool=pool,
            dev_eui=data.dev_eui,
            payload=data.payload,
            rssi=data.rssi,
            snr=data.snr,
        )
        return {"ok": True}
    except Exception as exc:
        logger.error(
            "Falha ao persistir telemetria para dev_eui=%s: %s",
            data.dev_eui,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database insertion error",
        ) from exc
```

- [ ] **Step 9: Atualizar `src/tenant/main.py`**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tenant.config import TenantSettings
from tenant.db import create_db_pool
from tenant.routers import ingest

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = TenantSettings()
    pool = None
    try:
        pool = await create_db_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
        )
        logger.info("Pool TimescaleDB inicializado.")
    except Exception as exc:
        logger.warning("TimescaleDB indisponivel no startup (%s).", exc)
    app.state.db_pool = pool

    yield

    if pool is not None:
        await pool.close()
        logger.info("Pool TimescaleDB encerrado.")


app = FastAPI(title="LINX Tenant App Template", lifespan=lifespan)
app.include_router(ingest.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 10: Rodar os testes e verificar que passam**

Run: `cd tenant_app_template && poetry run pytest tests/ -v`
Expected: PASS (`test_ingest.py` 3 testes + `test_main.py::test_read_health`).

- [ ] **Step 11: Rodar lint**

Run: `cd tenant_app_template && poetry run task lint`
Expected: `Success: no issues found` e sem erros de flake8.

- [ ] **Step 12: Commit**

```bash
git add tenant_app_template/pyproject.toml tenant_app_template/poetry.lock \
  tenant_app_template/src/tenant/config.py tenant_app_template/src/tenant/db.py \
  tenant_app_template/src/tenant/routers \
  tenant_app_template/src/tenant/main.py tenant_app_template/tests/test_ingest.py
git commit -m "feat(tenant): POST /ingest persiste telemetria no TimescaleDB (#36)"
```

---

## Task 3: middleware — `POST /ingest` (encaminhamento para o tenant_app)

**Files:**
- Modify: `client_agent_api/pyproject.toml`
- Modify: `client_agent_api/src/agent/config.py`
- Create: `client_agent_api/src/agent/routers/__init__.py`
- Create: `client_agent_api/src/agent/routers/ingest.py`
- Modify: `client_agent_api/src/agent/main.py`
- Test: `client_agent_api/tests/test_ingest_router.py`
- Test: `client_agent_api/tests/test_main.py`

- [ ] **Step 1: Mover `httpx` para dependências de runtime**

Em `client_agent_api/pyproject.toml`, adicione `httpx` a `dependencies`:

```toml
    "pydantic-settings (>=2.15.0,<3.0.0)",
    "httpx (>=0.27.0,<1.0.0)"
```

E remova a linha `"httpx (>=0.27.0,<1.0.0)",` do bloco
`[dependency-groups].dev`.

- [ ] **Step 2: Atualizar lock/instalação**

Run: `cd client_agent_api && poetry lock && poetry install`
Expected: lock atualizado e instalação sem erro.

- [ ] **Step 3: Adicionar settings do tenant**

Em `client_agent_api/src/agent/config.py`, adicione os campos:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    saas_grpc_host: str = "saas:50051"
    grpc_timeout_seconds: float = 5.0
    config_cache_ttl_seconds: float = 60.0
    tenant_app_url: str = "http://localhost:8002"
    ingest_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
```

- [ ] **Step 4: Escrever os testes que falham**

Crie `client_agent_api/tests/test_ingest_router.py`:

```python
import asyncio

import httpx
import pytest
from starlette.testclient import TestClient

from agent.main import app

client = TestClient(app)


@pytest.fixture
def install_transport():
    clients = []

    def _install(handler):
        http_client = httpx.AsyncClient(
            base_url="http://tenant.test",
            transport=httpx.MockTransport(handler),
        )
        clients.append(http_client)
        app.state.http_client = http_client
        return http_client

    yield _install

    for http_client in clients:
        asyncio.run(http_client.aclose())
    if hasattr(app.state, "http_client"):
        del app.state.http_client


def test_ingest_forwards_and_returns_201(install_transport):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(201, json={"ok": True})

    install_transport(handler)

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True}
    assert captured["url"] == "http://tenant.test/ingest"


def test_ingest_invalid_payload_returns_422(install_transport):
    install_transport(
        lambda request: httpx.Response(201, json={"ok": True})
    )

    response = client.post("/ingest", json={"dev_eui": "dev1"})

    assert response.status_code == 422


def test_ingest_propagates_upstream_422(install_transport):
    install_transport(
        lambda request: httpx.Response(422, json={"detail": "invalid"})
    )

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 422


def test_ingest_upstream_unreachable_returns_502(install_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    install_transport(handler)

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 502
```

Adicione a `client_agent_api/tests/test_main.py`:

```python
def test_lifespan_creates_and_closes_http_client():
    with patch("agent.main.SaasGrpcClient") as client_cls, patch(
        "agent.main.httpx.AsyncClient"
    ) as http_cls:
        client_cls.return_value.check_connectivity.return_value = True
        http_instance = http_cls.return_value
        http_instance.aclose = AsyncMock()

        with TestClient(app) as client:
            assert client.app.state.http_client is http_instance

        http_instance.aclose.assert_awaited_once()
```

E ajuste o import no topo de `test_main.py`:

```python
from unittest.mock import AsyncMock, patch
```

- [ ] **Step 5: Rodar os testes e verificar que falham**

Run: `cd client_agent_api && poetry run pytest tests/test_ingest_router.py tests/test_main.py -v`
Expected: FAIL (`/ingest` inexistente; `http_client` ausente no lifespan).

- [ ] **Step 6: Criar `src/agent/routers/__init__.py`**

Arquivo vazio (marca o pacote):

```python
```

- [ ] **Step 7: Criar `src/agent/routers/ingest.py`**

```python
"""Router de ingestao: valida e encaminha telemetria ao tenant app."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class TelemetryIn(BaseModel):
    """Schema de validacao para payload de telemetria."""

    dev_eui: str = Field(..., min_length=1)
    payload: dict[str, Any]
    rssi: int | None = None
    snr: float | None = None


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    data: TelemetryIn,
    request: Request,
) -> Any:
    """Encaminha o payload validado para o /ingest do tenant app."""
    http_client = getattr(request.app.state, "http_client", None)
    if http_client is None:
        logger.error("Cliente HTTP do tenant app indisponivel")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upstream client unavailable",
        )

    try:
        response = await http_client.post(
            "/ingest", json=data.model_dump()
        )
    except httpx.HTTPError as exc:
        logger.error("Falha ao encaminhar telemetria: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tenant app unreachable",
        ) from exc

    if response.status_code >= 500:
        logger.error("Tenant app retornou %s", response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tenant app error",
        )

    if response.status_code >= 400:
        detail = response.json().get("detail", "Invalid payload")
        raise HTTPException(
            status_code=response.status_code, detail=detail
        )

    return response.json()
```

- [ ] **Step 8: Atualizar `src/agent/main.py`**

Substitua o conteúdo por:

```python
import asyncio
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response, status

from agent.config import AgentSettings
from agent.grpc_client import SaasGrpcClient
from agent.routers import ingest

logger = logging.getLogger(__name__)

HEALTH_CACHE_TTL_SECONDS = 5.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AgentSettings()
    client = SaasGrpcClient(
        server=settings.saas_grpc_host,
        timeout=settings.grpc_timeout_seconds,
        cache_ttl_seconds=settings.config_cache_ttl_seconds,
    )
    connected = await asyncio.to_thread(client.check_connectivity)
    if connected:
        logger.info("SaaS Backend acessível em %s", settings.saas_grpc_host)
    app.state.saas_client = client
    app.state.saas_connected = connected
    app.state.saas_checked_at = time.monotonic()

    http_client = httpx.AsyncClient(
        base_url=settings.tenant_app_url,
        timeout=settings.ingest_timeout_seconds,
    )
    app.state.http_client = http_client

    yield

    await http_client.aclose()
    client.close()
    logger.info("Canal gRPC encerrado.")


app = FastAPI(title="LINX Client Agent API", lifespan=lifespan)
app.include_router(ingest.router)


async def _is_saas_connected(fastapi_app: FastAPI) -> bool:
    client = getattr(fastapi_app.state, "saas_client", None)
    if client is None:
        return False

    checked_at = getattr(fastapi_app.state, "saas_checked_at", None)
    now = time.monotonic()
    if checked_at is not None and now - checked_at < HEALTH_CACHE_TTL_SECONDS:
        return fastapi_app.state.saas_connected

    connected = await asyncio.to_thread(client.check_connectivity)
    fastapi_app.state.saas_connected = connected
    fastapi_app.state.saas_checked_at = now
    return connected


@app.get("/health")
async def health(request: Request, response: Response) -> dict:
    connected = await _is_saas_connected(request.app)
    if not connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if connected else "degraded",
        "saas_grpc": connected,
    }
```

- [ ] **Step 9: Rodar os testes e verificar que passam**

Run: `cd client_agent_api && poetry run pytest tests/ -v`
Expected: PASS (router + main + consumer existentes).

- [ ] **Step 10: Rodar lint**

Run: `cd client_agent_api && poetry run task lint`
Expected: `Success: no issues found` e sem erros de flake8.

- [ ] **Step 11: Commit**

```bash
git add client_agent_api/pyproject.toml client_agent_api/poetry.lock \
  client_agent_api/src/agent/config.py client_agent_api/src/agent/routers \
  client_agent_api/src/agent/main.py \
  client_agent_api/tests/test_ingest_router.py client_agent_api/tests/test_main.py
git commit -m "feat(agent): POST /ingest encaminha telemetria ao tenant app (#36)"
```

---

## Task 4: consumer — parse mínimo + POST para `/ingest`

**Files:**
- Modify: `client_agent_api/src/agent/mqtt_consumer.py`
- Test: `client_agent_api/tests/test_mqtt_consumer.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione a `client_agent_api/tests/test_mqtt_consumer.py`:

```python
import httpx


def test_on_message_posts_parsed_payload():
    consumer = _consumer_with_mock_client()
    consumer.http_client = MagicMock()
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b'{"dev_eui": "dev1", "payload": {"t": 20}}'

    consumer.on_message(consumer.client, None, message)

    consumer.http_client.post.assert_called_once_with(
        consumer.ingest_url,
        json={"dev_eui": "dev1", "payload": {"t": 20}},
    )


def test_on_message_invalid_json_does_not_post():
    consumer = _consumer_with_mock_client()
    consumer.http_client = MagicMock()
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b"not-json"

    consumer.on_message(consumer.client, None, message)

    consumer.http_client.post.assert_not_called()


def test_on_message_missing_fields_does_not_post():
    consumer = _consumer_with_mock_client()
    consumer.http_client = MagicMock()
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b'{"foo": 1}'

    consumer.on_message(consumer.client, None, message)

    consumer.http_client.post.assert_not_called()


def test_on_message_post_failure_is_logged(caplog):
    consumer = _consumer_with_mock_client()
    consumer.http_client = MagicMock()
    consumer.http_client.post.side_effect = httpx.ConnectError("boom")
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b'{"dev_eui": "dev1", "payload": {"t": 20}}'

    with caplog.at_level("ERROR"):
        consumer.on_message(consumer.client, None, message)

    assert "Falha ao encaminhar" in caplog.text
```

- [ ] **Step 2: Rodar os testes e verificar que falham**

Run: `cd client_agent_api && poetry run pytest tests/test_mqtt_consumer.py -v`
Expected: FAIL (`consumer.http_client`/`consumer.ingest_url` inexistentes e
`on_message` não faz POST).

- [ ] **Step 3: Implementar o parse + POST**

Substitua `client_agent_api/src/agent/mqtt_consumer.py` por:

```python
import json
import logging
import os
from typing import Any

import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_TOPIC = "application/+/device/+/event/up"
DEFAULT_INGEST_URL = "http://localhost:8001/ingest"


class MqttConsumer:
    def __init__(self) -> None:
        self.broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        self.broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self.topic = os.getenv("MQTT_TOPIC", DEFAULT_TOPIC)
        self.ingest_url = os.getenv("INGEST_URL", DEFAULT_INGEST_URL)
        self.http_client = httpx.Client(timeout=5.0)
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(
        self, client, userdata, connect_flags, reason_code, properties=None
    ) -> None:
        if reason_code == 0:
            logger.info(
                "Conectado ao broker MQTT %s:%s",
                self.broker_host,
                self.broker_port,
            )
            client.subscribe(self.topic)
            logger.info("Inscrito no tópico %s", self.topic)
        else:
            logger.error(
                "Falha ao conectar ao broker MQTT: reason_code=%s",
                reason_code,
            )

    @staticmethod
    def _parse_payload(raw: bytes) -> dict[str, Any] | None:
        try:
            data = json.loads(raw.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Payload MQTT inválido, ignorando: %s", exc)
            return None

        if (
            not isinstance(data, dict)
            or "dev_eui" not in data
            or "payload" not in data
        ):
            logger.warning(
                "Payload MQTT sem dev_eui/payload obrigatórios, ignorando."
            )
            return None

        telemetry: dict[str, Any] = {
            "dev_eui": data["dev_eui"],
            "payload": data["payload"],
        }
        if "rssi" in data:
            telemetry["rssi"] = data["rssi"]
        if "snr" in data:
            telemetry["snr"] = data["snr"]
        return telemetry

    def on_message(self, client, userdata, message) -> None:
        logger.info(
            "Uplink recebido no tópico %s: %s", message.topic, message.payload
        )
        telemetry = self._parse_payload(message.payload)
        if telemetry is None:
            return

        try:
            response = self.http_client.post(
                self.ingest_url, json=telemetry
            )
            response.raise_for_status()
            logger.info(
                "Telemetria encaminhada para /ingest (status=%s)",
                response.status_code,
            )
        except httpx.HTTPError as exc:
            logger.error(
                "Falha ao encaminhar telemetria para /ingest: %s", exc
            )

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.info("Desconectado do broker MQTT: reason_code=%s", reason_code)

    def start(self) -> None:
        self.client.connect(self.broker_host, self.broker_port)
        self.client.loop_forever()

    def stop(self) -> None:
        self.http_client.close()
        self.client.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    MqttConsumer().start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar os testes e verificar que passam**

Run: `cd client_agent_api && poetry run pytest tests/test_mqtt_consumer.py -v`
Expected: PASS (9 testes: 5 originais + 4 novos).

- [ ] **Step 5: Rodar lint**

Run: `cd client_agent_api && poetry run task lint`
Expected: `Success: no issues found` e sem erros de flake8.

- [ ] **Step 6: Commit**

```bash
git add client_agent_api/src/agent/mqtt_consumer.py \
  client_agent_api/tests/test_mqtt_consumer.py
git commit -m "feat(agent): consumer MQTT faz POST da telemetria em /ingest (#36)"
```

---

## Task 5: Documentação

**Files:**
- Modify: `client_agent_api/README.md`
- Modify: `tenant_app_template/README.md`
- Modify: `tenant_app_template/.env.example`

- [ ] **Step 1: Atualizar `client_agent_api/README.md`**

Na seção `📍 Endpoints`, adicione a linha:

```markdown
| `POST` | `/ingest` | Recebe telemetria validada e encaminha ao `/ingest` do tenant app. `201` em sucesso; `422` payload inválido; `502` tenant app inacessível. |
```

Na tabela de variáveis do middleware, adicione:

```markdown
| `TENANT_APP_URL`           | `http://localhost:8002` | URL base do tenant app (destino da ingestão).  |
| `INGEST_TIMEOUT_SECONDS`   | `5`            | Timeout (s) do encaminhamento ao tenant app.    |
```

Na seção `📡 Consumidor MQTT`, adicione a variável e a nota:

```markdown
| `INGEST_URL`        | `http://localhost:8001/ingest`       | Destino do POST de ingestão. |
```

> O consumer agora faz o parse mínimo (`dev_eui`, `payload`) e faz `POST` no
> `/ingest` do middleware, que encaminha ao tenant app.

Ajuste a nota do topo (linha 9) para refletir o estado atual:

```markdown
> Nesta sprint o consumer MQTT roda neste middleware e a persistência da
> telemetria vive no `tenant_app_template` (Model A). Mover o consumer ao SaaS
> Backend é a #47.
```

- [ ] **Step 2: Atualizar `tenant_app_template/README.md`**

Adicione uma seção `📥 Ingestão` com o endpoint, o contrato e o pipeline:

````markdown
## 📥 Ingestão

| Método | Rota      | Descrição                                                         |
| :----: | --------- | ----------------------------------------------------------------- |
| `POST` | `/ingest` | Valida o payload e persiste na hypertable `telemetry`. `201` em sucesso; `422` payload inválido; `503` banco indisponível. |

Corpo esperado:

```json
{"dev_eui": "dev1", "payload": {"t": 20}, "rssi": -70, "snr": 7.5}
```

Pipeline: `Mosquitto → mqtt_consumer (client_agent_api) → POST /ingest
(client_agent_api) → POST /ingest (tenant_app) → TimescaleDB`.

Variáveis de ambiente de banco: `DB_HOST` (default `timescaledb`; em dev fora do
Docker use `localhost`), `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
````

- [ ] **Step 3: Atualizar `tenant_app_template/.env.example`**

Adicione ao final do arquivo:

```
# Conexão com o TimescaleDB (dentro do docker-compose use "timescaledb").
DB_HOST=timescaledb
DB_PORT=5432
```

- [ ] **Step 4: Commit**

```bash
git add client_agent_api/README.md tenant_app_template/README.md \
  tenant_app_template/.env.example
git commit -m "docs: pipeline de ingestão MQTT → /ingest → TimescaleDB (#36)"
```

---

## Task 6: Verificação ponta-a-ponta e gate final

**Files:** nenhum (verificação).

- [ ] **Step 1: Subir o broker MQTT**

Run: `docker compose -f infra/docker-compose.base.yml up -d mosquitto`
Expected: container `mosquitto` rodando na porta `1883`.

- [ ] **Step 2: Subir tenant_app + TimescaleDB**

Run: `cd tenant_app_template && cp -n .env.example .env; docker compose up -d --build`
Expected: `timescaledb` healthy e `tenant_app` na porta host `8002`.

- [ ] **Step 3: Subir o middleware**

Run: `cd client_agent_api && poetry run uvicorn agent.main:app --port 8001`
Expected: serviço ouvindo em `http://localhost:8001`.

- [ ] **Step 4: Subir o consumer MQTT**

Run (outro terminal): `cd client_agent_api && poetry run python -m agent.mqtt_consumer`
Expected: log `Inscrito no tópico application/+/device/+/event/up`.

- [ ] **Step 5: Publicar o uplink de teste**

Run:

```bash
mosquitto_pub -h localhost -p 1883 \
  -t "application/1/device/dev1/event/up" \
  -m '{"dev_eui":"dev1","payload":{"t":20}}'
```

Expected no log do consumer: `Telemetria encaminhada para /ingest`.

- [ ] **Step 6: Confirmar a linha no TimescaleDB**

Run:

```bash
docker compose -f tenant_app_template/docker-compose.yml exec timescaledb \
  psql -U tenant -d tenantdb -c "SELECT dev_eui, payload, rssi, snr FROM telemetry;"
```

Expected: uma linha com `dev1` e `{"t": 20}`.

- [ ] **Step 7: Verificar o `422`**

Run:

```bash
curl -i -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" -d '{"dev_eui":"x"}'
```

Expected: `HTTP/1.1 422 Unprocessable Entity`.

- [ ] **Step 8: Gate final de lint e testes**

Run: `cd tenant_app_template && poetry run task lint && poetry run task test`
Run: `cd client_agent_api && poetry run task lint && poetry run task test`
Expected: ambos verdes.

- [ ] **Step 9: (Pós-merge, com autorização) Atualizar o PROGRESS.md**

Somente após fechar a issue #36 e com autorização explícita do usuário:

Run: `make progress`
Expected: `PROGRESS.md atualizado: ...` com a #36 marcada.

---

## Self-Review

**Spec coverage:**
- `/ingest` no tenant_app persistindo → Task 2. ✔
- `/ingest` no middleware encaminhando → Task 3. ✔
- Consumer parse + POST → Task 4. ✔
- 422 / 502 / 503 → Tasks 2–3 (testes) e Task 6 (e2e). ✔
- Envs `TENANT_APP_URL`/`INGEST_URL` → Tasks 3–5. ✔
- Docs → Task 5. ✔
- Verificação `mosquitto_pub` + `SELECT` → Task 6. ✔

**Placeholder scan:** sem `TBD`/`TODO`; todos os passos de código têm o código
completo.

**Type consistency:** `TelemetryIn` (`dev_eui`, `payload`, `rssi`, `snr`) é
idêntico nas Tasks 2 e 3; `insert_telemetry(pool, dev_eui, payload, rssi, snr)`
consistente entre `db.py` e o router; `ingest_url`/`http_client` consistentes na
Task 4.
