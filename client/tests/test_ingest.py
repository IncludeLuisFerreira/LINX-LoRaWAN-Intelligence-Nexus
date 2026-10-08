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
