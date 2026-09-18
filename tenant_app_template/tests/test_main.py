from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from tenant.grpc_client import TenantBootstrapError
from tenant.main import app


@contextmanager
def _mock_startup():
    pool = MagicMock()
    pool.close = AsyncMock()
    with (
        patch("tenant.main.create_db_pool", return_value=pool),
        patch("tenant.main.SaasConfigClient") as client_cls,
    ):
        yield pool, client_cls.return_value


def test_read_health():
    with _mock_startup():
        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_calls_get_app_config():
    with _mock_startup() as (_, client):
        with TestClient(app):
            pass

    client.get_app_config.assert_called_once_with("app-abc123")
    client.close.assert_called_once()


def test_lifespan_survives_get_app_config_failure():
    with _mock_startup() as (_, client):
        client.get_app_config.side_effect = TenantBootstrapError("boom")
        with TestClient(app) as test_client:
            response = test_client.get("/health")

    assert response.status_code == 200
    client.close.assert_called_once()
