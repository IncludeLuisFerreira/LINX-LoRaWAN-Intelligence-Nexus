import asyncio

import pytest
from fastapi.testclient import TestClient

from telemetry_consumer.app import create_app


class FakePool:
    def __init__(self, *, ping=1, error=None):
        self._ping = ping
        self._error = error

    async def fetchval(self, query):
        if self._error is not None:
            raise self._error
        return self._ping

    async def close(self):
        pass


class FakeConsumer:
    connected = True

    def __init__(self, *args, **kwargs):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def health(self):
        return {
            "rabbitmq_connected": self.connected,
            "processed": 2,
            "failed": 0,
            "last_processed_at": "2026-10-08T12:00:00Z",
            "last_error": None,
        }


class DisconnectedConsumer(FakeConsumer):
    connected = False


class LeakyConsumer(FakeConsumer):
    def health(self):
        data = super().health()
        data["last_error"] = (
            "amqp://tenant.secret-user:secret-pass@rabbitmq:5672/%2f"
        )
        return data


async def _fake_pool_factory(**kwargs):
    return FakePool()


async def _failing_pool_factory(**kwargs):
    raise RuntimeError("db down")


async def _broken_ping_pool_factory(**kwargs):
    return FakePool(error=RuntimeError("db down"))


async def _timeout_ping_pool_factory(**kwargs):
    return FakePool(error=asyncio.TimeoutError())


async def _fake_probe(**kwargs):
    return True


async def _failing_probe(**kwargs):
    return False


def test_health_reports_consumer_state():
    app = create_app(
        pool_factory=_fake_pool_factory,
        consumer_factory=FakeConsumer,
        db_probe=_fake_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["mqtt"] is True
    assert body["db_ok"] == body["db"]
    assert body["rabbitmq_connected"] == body["mqtt"]
    assert body["processed"] == 2
    assert body["failed"] == 0
    assert body["last_processed_at"] == "2026-10-08T12:00:00Z"
    assert body["ws_connections"] == 0


def test_health_returns_503_when_db_unavailable():
    app = create_app(
        pool_factory=_failing_pool_factory,
        consumer_factory=FakeConsumer,
        db_probe=_failing_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] is False
    assert body["mqtt"] is True


def test_health_returns_503_when_db_ping_fails():
    app = create_app(
        pool_factory=_broken_ping_pool_factory,
        consumer_factory=FakeConsumer,
        db_probe=_failing_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] is False
    assert body["mqtt"] is True


def test_health_recovers_pool_without_message_traffic():
    calls = {"count": 0}

    async def flaky_factory(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("db down at startup")
        return FakePool()

    app = create_app(
        pool_factory=flaky_factory,
        consumer_factory=FakeConsumer,
        db_probe=_fake_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert calls["count"] == 2


def test_health_uses_probe_when_pool_ping_times_out():
    app = create_app(
        pool_factory=_timeout_ping_pool_factory,
        consumer_factory=FakeConsumer,
        db_probe=_fake_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] is True


def test_health_returns_503_when_timeout_and_probe_fail():
    app = create_app(
        pool_factory=_timeout_ping_pool_factory,
        consumer_factory=FakeConsumer,
        db_probe=_failing_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] is False


def test_health_does_not_expose_consumer_last_error():
    app = create_app(
        pool_factory=_fake_pool_factory,
        consumer_factory=LeakyConsumer,
        db_probe=_fake_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    body = response.json()
    assert "last_error" not in body
    assert "secret-pass" not in response.text
    assert "tenant.secret-user" not in response.text


def test_health_returns_503_when_consumer_disconnected():
    app = create_app(
        pool_factory=_fake_pool_factory,
        consumer_factory=DisconnectedConsumer,
        db_probe=_fake_probe,
    )
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] is True
    assert body["mqtt"] is False


def test_lifespan_starts_and_stops_consumer():
    events = {}

    class TrackingConsumer(FakeConsumer):
        def start(self):
            events["started"] = True

        def stop(self):
            events["stopped"] = True

    app = create_app(
        pool_factory=_fake_pool_factory, consumer_factory=TrackingConsumer
    )
    with TestClient(app):
        assert events.get("started") is True
    assert events.get("stopped") is True


class InsertPool:
    def __init__(self):
        self.executed = []

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, query, *args):
                pool.executed.append(args)
                return "INSERT 0 1"

        return _Ctx()

    async def close(self):
        pass


class RecordingWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


async def test_handler_persists_and_broadcasts():
    captured = {}
    pool = InsertPool()

    class CapturingConsumer(FakeConsumer):
        def __init__(self, settings, loop, handler, *args, **kwargs):
            super().__init__()
            captured["handler"] = handler

    async def pool_factory(**kwargs):
        return pool

    app = create_app(
        pool_factory=pool_factory, consumer_factory=CapturingConsumer
    )
    with TestClient(app):
        ws = RecordingWebSocket()
        await app.state.broadcaster.register(ws)
        result = await captured["handler"](
            {
                "app_id": "app-abc123",
                "dev_eui": "dev1",
                "event_type": "reading",
                "payload": {"temperature": 21},
                "timestamp": "2026-10-08T12:00:00Z",
            }
        )
        assert result is True
        assert len(pool.executed) == 1
        assert len(ws.messages) == 1
        record = ws.messages[0]
        assert record["dev_eui"] == "dev1"
        assert record["time"] == "2026-10-08T12:00:00Z"
        assert record["rssi"] is None
        assert record["snr"] is None


ENVELOPE = {
    "app_id": "app-abc123",
    "dev_eui": "dev1",
    "event_type": "reading",
    "payload": {"temperature": 21},
    "timestamp": "2026-10-08T12:00:00Z",
}


async def test_lazy_pool_recovery_recreates_pool():
    captured = {}
    state = {"calls": 0}

    async def flaky_factory(**kwargs):
        state["calls"] += 1
        if state["calls"] < 3:
            raise RuntimeError("db down")
        return InsertPool()

    class CapturingConsumer(FakeConsumer):
        def __init__(self, settings, loop, handler, *args, **kwargs):
            super().__init__()
            captured["handler"] = handler

    app = create_app(
        pool_factory=flaky_factory, consumer_factory=CapturingConsumer
    )
    with TestClient(app):
        assert app.state.db_pool is None
        with pytest.raises(RuntimeError):
            await captured["handler"](ENVELOPE)
        assert app.state.db_pool is None
        assert await captured["handler"](ENVELOPE) is True
        assert app.state.db_pool is not None
    assert state["calls"] == 3
