# Client Agent API — gRPC Client do Gateway (Modelo A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o `client_agent_api` de agente por-tenant (Modelo B) em gateway compartilhado (Modelo A) com client gRPC, checagem de conectividade no startup e resolução de `GetAppConfig(app_id)` sob demanda com cache.

**Architecture:** O `client_agent_api` passa a ser um gateway único entre frontend/integrações e os contêineres isolados por aplicação. No startup ele valida a conectividade gRPC com o SaaS Backend e aguarda requisições; a config de cada tenant é resolvida sob demanda via `GetAppConfig(app_id)` com cache TTL. A ingestão MQTT deixa de viver no gateway (vai para o `tenant_app_template` em issue futura).

**Tech Stack:** Python 3.12, FastAPI, grpcio, protobuf, pydantic-settings, pytest, mypy, black, isort, flake8, taskipy.

**Issue:** #34 (reescrita para o Modelo A)

**Fora de escopo:** ingestão MQTT no tenant, gRPC server do gateway (`IngestTelemetry`/`SyncRule`), proxy REST/WebSocket, JWT/RBAC, TLS, `application_instances`/`agent_endpoint`.

---

## Decisões

1. Conectividade no startup **não** derruba o gateway: loga e continua; `/health` reporta `saas_grpc`.
2. `TenantRuntimeConfig` mantém `db_host`/`db_port`/`mqtt_topic` (contrato atual). `agent_endpoint`/`agent_port` entram na Fase 5.
3. `mqtt_consumer.py` permanece no repo nesta issue; a movimentação para o tenant é a Fase 1.

## File Structure

- Modify: `client_agent_api/src/agent/config.py` — settings do gateway, sem `app_id`.
- Rewrite: `client_agent_api/src/agent/grpc_client.py` — `SaasGrpcClient` (connectivity + resolver + cache).
- Modify: `client_agent_api/src/agent/main.py` — lifespan cria client, valida conectividade, expõe `app.state`.
- Modify: `client_agent_api/tests/conftest.py` — remove `APP_ID`.
- Add: `client_agent_api/tests/test_config.py`.
- Rewrite: `client_agent_api/tests/test_grpc_client.py`.
- Modify: `client_agent_api/tests/test_main.py`.
- Modify: `client_agent_api/pyproject.toml` — adiciona `types-protobuf`.

---

### Task 1: Settings do gateway sem `app_id`

**Files:**
- Modify: `client_agent_api/src/agent/config.py`
- Test: `client_agent_api/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from agent.config import AgentSettings


def test_settings_have_no_app_id():
    settings = AgentSettings()
    assert not hasattr(settings, "app_id")
    assert settings.saas_grpc_host == "localhost:50051"
    assert settings.config_cache_ttl_seconds == 60.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (`config_cache_ttl_seconds` inexistente / `app_id` presente)

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    saas_grpc_host: str = "saas:50051"
    grpc_timeout_seconds: float = 5.0
    config_cache_ttl_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client_agent_api/src/agent/config.py client_agent_api/tests/test_config.py
git commit -m "refactor(agent): settings do gateway sem app_id"
```

### Task 2: `SaasGrpcClient.get_app_config` + mapeamento

**Files:**
- Rewrite: `client_agent_api/src/agent/grpc_client.py`
- Rewrite: `client_agent_api/tests/test_grpc_client.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import MagicMock, patch

import grpc
import pytest

from agent.grpc import saas_agent_pb2
from agent.grpc_client import (
    AgentBootstrapError,
    SaasGrpcClient,
    TenantRuntimeConfig,
)


def _client(stub: MagicMock) -> SaasGrpcClient:
    with patch("agent.grpc_client.grpc.insecure_channel"), patch(
        "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub",
        return_value=stub,
    ):
        return SaasGrpcClient(
            server="localhost:50051", timeout=1.0, cache_ttl_seconds=60.0
        )


def test_get_app_config_maps_response():
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        db_host="postgres-tenant", db_port=5432, mqtt_topic="app/tenant1/#"
    )
    client = _client(stub)

    config = client.get_app_config("tenant1")

    assert config == TenantRuntimeConfig(
        "postgres-tenant", 5432, "app/tenant1/#"
    )
    stub.GetAppConfig.assert_called_once()


def test_get_app_config_rpc_error_raises_bootstrap_error():
    stub = MagicMock()
    error = grpc.RpcError()
    error.code = lambda: grpc.StatusCode.NOT_FOUND
    error.details = lambda: "Aplicação não encontrada"
    stub.GetAppConfig.side_effect = error
    client = _client(stub)

    with pytest.raises(AgentBootstrapError) as exc:
        client.get_app_config("missing")

    assert "NOT_FOUND" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grpc_client.py -v`
Expected: FAIL (`SaasGrpcClient` inexistente)

- [ ] **Step 3: Write minimal implementation**

```python
import logging
import time
from dataclasses import dataclass

import grpc

from agent.grpc import saas_agent_pb2, saas_agent_pb2_grpc

logger = logging.getLogger(__name__)


class AgentBootstrapError(RuntimeError):
    """Falha de comunicação com o SaaS Backend."""


@dataclass(frozen=True)
class TenantRuntimeConfig:
    db_host: str
    db_port: int
    mqtt_topic: str


class SaasGrpcClient:
    def __init__(
        self,
        server: str,
        timeout: float = 5.0,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self._server = server
        self._timeout = timeout
        self._cache_ttl = cache_ttl_seconds
        self._channel = grpc.insecure_channel(server)
        self._stub = saas_agent_pb2_grpc.AgentBridgeStub(self._channel)
        self._cache: dict[str, tuple[TenantRuntimeConfig, float]] = {}

    def get_app_config(self, app_id: str) -> TenantRuntimeConfig:
        now = time.monotonic()
        cached = self._cache.get(app_id)
        if cached is not None and cached[1] > now:
            return cached[0]

        request = saas_agent_pb2.AppId(  # type: ignore[attr-defined]
            app_id=app_id
        )
        try:
            response = self._stub.GetAppConfig(request, timeout=self._timeout)
        except grpc.RpcError as rpc_err:
            code = rpc_err.code() if hasattr(rpc_err, "code") else "UNKNOWN"
            details = (
                rpc_err.details()
                if hasattr(rpc_err, "details")
                else str(rpc_err)
            )
            logger.critical(
                "Falha gRPC GetAppConfig app_id=%s code=%s details=%s",
                app_id,
                code,
                details,
            )
            raise AgentBootstrapError(
                f"Falha ao obter AppConfig ({code}): {details}"
            ) from rpc_err

        config = TenantRuntimeConfig(
            db_host=response.db_host,
            db_port=response.db_port,
            mqtt_topic=response.mqtt_topic,
        )
        self._cache[app_id] = (config, now + self._cache_ttl)
        return config

    def close(self) -> None:
        self._channel.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grpc_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client_agent_api/src/agent/grpc_client.py client_agent_api/tests/test_grpc_client.py
git commit -m "feat(agent): SaasGrpcClient com GetAppConfig sob demanda"
```

### Task 3: Cache com TTL

**Files:**
- Test: `client_agent_api/tests/test_grpc_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_get_app_config_uses_cache():
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        db_host="h", db_port=1, mqtt_topic="t"
    )
    client = _client(stub)

    client.get_app_config("tenant1")
    client.get_app_config("tenant1")

    assert stub.GetAppConfig.call_count == 1


def test_get_app_config_refreshes_after_ttl():
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        db_host="h", db_port=1, mqtt_topic="t"
    )
    client = _client(stub)

    with patch(
        "agent.grpc_client.time.monotonic", side_effect=[0.0, 0.0, 61.0]
    ):
        client.get_app_config("tenant1")
        client.get_app_config("tenant1")

    assert stub.GetAppConfig.call_count == 2
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_grpc_client.py -v`
Expected: PASS (cache já implementado na Task 2; ajustar se necessário)

- [ ] **Step 3: Commit**

```bash
git add client_agent_api/tests/test_grpc_client.py
git commit -m "test(agent): cobre cache TTL do GetAppConfig"
```

### Task 4: `check_connectivity()`

**Files:**
- Modify: `client_agent_api/src/agent/grpc_client.py`
- Test: `client_agent_api/tests/test_grpc_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_check_connectivity_true_when_ready():
    future = MagicMock()
    future.result.return_value = None
    with patch("agent.grpc_client.grpc.insecure_channel"), patch(
        "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"
    ), patch(
        "agent.grpc_client.grpc.channel_ready_future", return_value=future
    ):
        client = SaasGrpcClient("localhost:50051", timeout=1.0)
    assert client.check_connectivity() is True


def test_check_connectivity_false_on_timeout():
    future = MagicMock()
    future.result.side_effect = grpc.FutureTimeoutError()
    with patch("agent.grpc_client.grpc.insecure_channel"), patch(
        "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"
    ), patch(
        "agent.grpc_client.grpc.channel_ready_future", return_value=future
    ):
        client = SaasGrpcClient("localhost:50051", timeout=1.0)
    assert client.check_connectivity() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_grpc_client.py -v`
Expected: FAIL (`check_connectivity` inexistente)

- [ ] **Step 3: Write minimal implementation**

Adicionar ao `SaasGrpcClient`:

```python
    def check_connectivity(self) -> bool:
        try:
            grpc.channel_ready_future(self._channel).result(
                timeout=self._timeout
            )
            return True
        except grpc.FutureTimeoutError:
            logger.critical("SaaS Backend inacessível em %s", self._server)
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_grpc_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client_agent_api/src/agent/grpc_client.py client_agent_api/tests/test_grpc_client.py
git commit -m "feat(agent): check_connectivity no SaasGrpcClient"
```

### Task 5: Lifespan + `/health`

**Files:**
- Modify: `client_agent_api/src/agent/main.py`
- Modify: `client_agent_api/tests/conftest.py`
- Modify: `client_agent_api/tests/test_main.py`

- [ ] **Step 1: Update conftest (remove APP_ID)**

```python
import pytest


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SAAS_GRPC_HOST", "localhost:50051")
```

- [ ] **Step 2: Write the failing tests**

```python
from unittest.mock import patch

from starlette.testclient import TestClient

from agent.main import app


def test_health_reports_saas_connectivity():
    with patch("agent.main.SaasGrpcClient") as client_cls:
        client_cls.return_value.check_connectivity.return_value = True
        with TestClient(app) as client:
            assert client.get("/health").json() == {
                "status": "ok",
                "saas_grpc": True,
            }


def test_lifespan_registers_and_closes_client():
    with patch("agent.main.SaasGrpcClient") as client_cls:
        instance = client_cls.return_value
        instance.check_connectivity.return_value = False
        with TestClient(app) as client:
            assert client.app.state.saas_client is instance
            assert client.app.state.saas_connected is False
        instance.close.assert_called_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL

- [ ] **Step 4: Write minimal implementation**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.config import AgentSettings
from agent.grpc_client import SaasGrpcClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AgentSettings()
    client = SaasGrpcClient(
        server=settings.saas_grpc_host,
        timeout=settings.grpc_timeout_seconds,
        cache_ttl_seconds=settings.config_cache_ttl_seconds,
    )
    connected = client.check_connectivity()
    if connected:
        logger.info("SaaS Backend acessível em %s", settings.saas_grpc_host)
    app.state.saas_client = client
    app.state.saas_connected = connected

    yield

    client.close()
    logger.info("Canal gRPC encerrado.")


app = FastAPI(title="LINX Client Agent API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "saas_grpc": getattr(app.state, "saas_connected", False),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add client_agent_api/src/agent/main.py client_agent_api/tests/conftest.py client_agent_api/tests/test_main.py
git commit -m "refactor(agent): gateway valida conectividade no lifespan"
```

### Task 6: Dependência `types-protobuf` + gate final

**Files:**
- Modify: `client_agent_api/pyproject.toml`

- [ ] **Step 1: Add dev dependency**

Em `[dependency-groups].dev`:

```toml
    "types-protobuf (>=7.35.0,<8.0.0)",
```

- [ ] **Step 2: Update lock**

Run: `poetry lock && poetry install`

- [ ] **Step 3: Run mypy**

Run: `poetry run mypy src/ tests/`
Expected: `Success: no issues found`

- [ ] **Step 4: Run full gate**

Run: `poetry run task lint && poetry run task test`
Expected: verde

- [ ] **Step 5: Commit**

```bash
git add client_agent_api/pyproject.toml client_agent_api/poetry.lock
git commit -m "chore(agent): adiciona types-protobuf ao dev"
```
