import asyncio
import contextlib

import pytest
import uvicorn
import websockets
from fastapi.testclient import TestClient
from websockets.exceptions import ConnectionClosed

from telemetry_consumer.app import create_app
from telemetry_consumer.broadcaster import Broadcaster
from telemetry_consumer.routers.telemetry import SERVICE_TOKEN_HEADER

TOKEN = "ci-service-token"
AUTH = {SERVICE_TOKEN_HEADER: TOKEN}


class FakeConsumer:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def health(self):
        return {
            "rabbitmq_connected": False,
            "processed": 0,
            "failed": 0,
            "last_processed_at": None,
            "last_error": None,
        }


async def _fake_pool_factory(**kwargs):
    return None


def _make_app():
    return create_app(
        pool_factory=_fake_pool_factory, consumer_factory=FakeConsumer
    )


def _client(app):
    return TestClient(app, headers=AUTH)


class FakePool:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def fetch(self, *args):
                pool.calls.append(args)
                return pool.rows

        return _Ctx()


def test_get_telemetry_returns_items():
    app = _make_app()
    app.state.db_pool = FakePool([{"dev_eui": "dev1"}])
    client = _client(app)
    response = client.get("/telemetry?dev_eui=dev1&limit=10")
    assert response.status_code == 200
    assert response.json()["items"] == [{"dev_eui": "dev1"}]
    assert response.json()["next_cursor"] is None


def test_get_telemetry_next_cursor_from_last_item():
    app = _make_app()
    app.state.db_pool = FakePool(
        [
            {
                "dev_eui": "dev1",
                "event_type": "up",
                "time": "2026-10-08T12:00:00Z",
            },
            {
                "dev_eui": "dev1",
                "event_type": "up",
                "time": "2026-10-08T11:00:00Z",
            },
        ]
    )
    client = _client(app)
    response = client.get("/telemetry")
    assert response.status_code == 200
    assert response.json()["next_cursor"] == "2026-10-08T11:00:00Z|dev1|up"


def test_get_telemetry_invalid_before_returns_422():
    app = _make_app()
    app.state.db_pool = FakePool([])
    client = _client(app)
    response = client.get("/telemetry?before=not-a-date")
    assert response.status_code == 422


def test_get_telemetry_accepts_composite_before():
    app = _make_app()
    pool = FakePool([])
    app.state.db_pool = pool
    client = _client(app)
    response = client.get("/telemetry?before=2026-10-08T12:00:00Z|dev1|up")
    assert response.status_code == 200
    assert pool.calls[0][2] == "app-abc123"
    assert pool.calls[0][4] == "2026-10-08T12:00:00Z"
    assert pool.calls[0][5] == "dev1"
    assert pool.calls[0][6] == "up"


def test_get_telemetry_scopes_query_to_settings_app_id():
    app = _make_app()
    pool = FakePool([])
    app.state.db_pool = pool
    client = _client(app)
    assert client.get("/telemetry").status_code == 200
    assert pool.calls[0][1] == 100
    assert pool.calls[0][2] == "app-abc123"


def test_get_telemetry_clamps_limit():
    app = _make_app()
    pool = FakePool([])
    app.state.db_pool = pool
    client = _client(app)
    assert client.get("/telemetry?limit=5000").status_code == 200
    assert pool.calls[0][1] == 1000
    assert client.get("/telemetry?limit=0").status_code == 200
    assert pool.calls[1][1] == 1


def test_get_telemetry_returns_503_without_pool():
    app = _make_app()
    client = _client(app)
    response = client.get("/telemetry")
    assert response.status_code == 503


def test_get_telemetry_requires_token():
    app = _make_app()
    app.state.db_pool = FakePool([])
    client = TestClient(app)
    assert client.get("/telemetry").status_code == 401


def test_get_telemetry_rejects_invalid_token():
    app = _make_app()
    app.state.db_pool = FakePool([])
    client = TestClient(app, headers={SERVICE_TOKEN_HEADER: "wrong-token"})
    assert client.get("/telemetry").status_code == 401


@pytest.fixture
async def live_server(monkeypatch):
    """Sobe um uvicorn real numa porta efêmera e rastreia registros no WS."""
    app = _make_app()
    register_calls = []
    original_register = Broadcaster.register

    async def tracking_register(self, websocket):
        register_calls.append(websocket)
        await original_register(self, websocket)

    monkeypatch.setattr(Broadcaster, "register", tracking_register)

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    try:
        for _ in range(500):
            if server.started:
                break
            if serve_task.done():
                serve_task.result()
            await asyncio.sleep(0.01)
        else:
            pytest.fail("uvicorn did not start")
        port = server.servers[0].sockets[0].getsockname()[1]
        yield app, f"ws://127.0.0.1:{port}", register_calls
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(serve_task, timeout=10)
        except asyncio.TimeoutError:
            serve_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await serve_task


async def _expect_close(url, code, headers=None):
    with pytest.raises(ConnectionClosed) as exc:
        ws = await websockets.connect(url, additional_headers=headers)
        try:
            await ws.recv()
        finally:
            await ws.close()
    assert exc.value.rcvd is not None
    assert exc.value.rcvd.code == code


async def test_ws_live_rejects_missing_token_with_4401(live_server):
    app, base_url, register_calls = live_server
    await _expect_close(f"{base_url}/ws/telemetry/app-abc123", 4401)
    assert register_calls == []
    assert app.state.broadcaster.count == 0


async def test_ws_live_rejects_invalid_token_with_4401(live_server):
    app, base_url, register_calls = live_server
    await _expect_close(
        f"{base_url}/ws/telemetry/app-abc123",
        4401,
        headers={SERVICE_TOKEN_HEADER: "wrong-token"},
    )
    assert register_calls == []
    assert app.state.broadcaster.count == 0


async def test_ws_live_rejects_wrong_app_id_with_1008(live_server):
    app, base_url, register_calls = live_server
    # app_id diferente de settings.app_id (default app-abc123)
    await _expect_close(
        f"{base_url}/ws/telemetry/outro-app", 1008, headers=AUTH
    )
    assert register_calls == []
    assert app.state.broadcaster.count == 0


async def test_ws_live_accepts_valid_connection_and_unregisters(live_server):
    app, base_url, register_calls = live_server
    broadcaster = app.state.broadcaster
    ws = await websockets.connect(
        f"{base_url}/ws/telemetry/app-abc123", additional_headers=AUTH
    )
    try:
        for _ in range(100):
            if broadcaster.count == 1:
                break
            await asyncio.sleep(0.01)
        assert broadcaster.count == 1
        assert len(register_calls) == 1
        await ws.send("ping")
        await asyncio.sleep(0.05)
        assert broadcaster.count == 1
    finally:
        await ws.close()
    for _ in range(100):
        if broadcaster.count == 0:
            break
        await asyncio.sleep(0.01)
    assert broadcaster.count == 0
