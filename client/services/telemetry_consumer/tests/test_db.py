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
