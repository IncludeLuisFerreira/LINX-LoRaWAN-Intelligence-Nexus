import pytest
from fastapi.testclient import TestClient

from telemetry_consumer.app import create_app
from telemetry_consumer.broadcaster import Broadcaster


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
    app = create_app()
    app.state.db_pool = FakePool([{"dev_eui": "dev1"}])
    client = TestClient(app)
    response = client.get("/telemetry?dev_eui=dev1&limit=10")
    assert response.status_code == 200
    assert response.json()["items"] == [{"dev_eui": "dev1"}]
    assert response.json()["next_cursor"] is None


def test_get_telemetry_next_cursor_from_last_item():
    app = create_app()
    app.state.db_pool = FakePool(
        [
            {"dev_eui": "dev1", "time": "2026-10-08T12:00:00Z"},
            {"dev_eui": "dev1", "time": "2026-10-08T11:00:00Z"},
        ]
    )
    client = TestClient(app)
    response = client.get("/telemetry")
    assert response.status_code == 200
    assert response.json()["next_cursor"] == "2026-10-08T11:00:00Z"


def test_get_telemetry_clamps_limit():
    app = create_app()
    pool = FakePool([])
    app.state.db_pool = pool
    client = TestClient(app)
    assert client.get("/telemetry?limit=5000").status_code == 200
    assert pool.calls[0][1] == 1000
    assert client.get("/telemetry?limit=0").status_code == 200
    assert pool.calls[1][1] == 1


def test_get_telemetry_returns_503_without_pool():
    app = create_app()
    client = TestClient(app)
    response = client.get("/telemetry")
    assert response.status_code == 503


def test_ws_rejects_wrong_app_id():
    app = create_app()
    app.state.broadcaster = Broadcaster()
    client = TestClient(app)
    # app_id diferente de settings.app_id (default app-abc123)
    with client.websocket_connect("/ws/telemetry/outro-app") as ws:
        with pytest.raises(Exception):
            ws.receive_json()


def test_ws_accepts_valid_app_id_and_unregisters():
    app = create_app()
    broadcaster = Broadcaster()
    app.state.broadcaster = broadcaster
    client = TestClient(app)
    with client.websocket_connect("/ws/telemetry/app-abc123") as ws:
        ws.send_text("ping")
    assert broadcaster.count == 0
