import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from telemetry_consumer.app import create_app
from telemetry_consumer.broadcaster import Broadcaster


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
    client = TestClient(app)
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
    client = TestClient(app)
    response = client.get("/telemetry")
    assert response.status_code == 200
    assert response.json()["next_cursor"] == "2026-10-08T11:00:00Z|dev1|up"


def test_get_telemetry_invalid_before_returns_422():
    app = _make_app()
    app.state.db_pool = FakePool([])
    client = TestClient(app)
    response = client.get("/telemetry?before=not-a-date")
    assert response.status_code == 422


def test_get_telemetry_accepts_composite_before():
    app = _make_app()
    pool = FakePool([])
    app.state.db_pool = pool
    client = TestClient(app)
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
    client = TestClient(app)
    assert client.get("/telemetry").status_code == 200
    assert pool.calls[0][1] == 100
    assert pool.calls[0][2] == "app-abc123"


def test_get_telemetry_clamps_limit():
    app = _make_app()
    pool = FakePool([])
    app.state.db_pool = pool
    client = TestClient(app)
    assert client.get("/telemetry?limit=5000").status_code == 200
    assert pool.calls[0][1] == 1000
    assert client.get("/telemetry?limit=0").status_code == 200
    assert pool.calls[1][1] == 1


def test_get_telemetry_returns_503_without_pool():
    app = _make_app()
    client = TestClient(app)
    response = client.get("/telemetry")
    assert response.status_code == 503


def test_ws_rejects_wrong_app_id():
    app = _make_app()
    app.state.broadcaster = Broadcaster()
    client = TestClient(app)
    # app_id diferente de settings.app_id (default app-abc123)
    with client.websocket_connect("/ws/telemetry/outro-app") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1008


def test_ws_accepts_valid_app_id_and_unregisters():
    app = _make_app()
    broadcaster = Broadcaster()
    app.state.broadcaster = broadcaster
    client = TestClient(app)
    with client.websocket_connect("/ws/telemetry/app-abc123") as ws:
        for _ in range(100):
            if broadcaster.count == 1:
                break
            time.sleep(0.01)
        assert broadcaster.count == 1
        ws.send_text("ping")
    assert broadcaster.count == 0
