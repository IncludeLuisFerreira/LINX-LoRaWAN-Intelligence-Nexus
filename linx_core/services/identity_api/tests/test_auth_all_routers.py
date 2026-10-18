from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from linx_shared.core.config import settings as shared_settings
from linx_shared.db.base import engine, get_db
from sqlalchemy.orm import Session

from identity_api.dependencies import get_chirpstack_client
from identity_api.main import app
from tests.auth import AUTH
from tests.fakes import FakeChirpStackClient

client = TestClient(app)
auth_client = TestClient(app, headers=AUTH)


@pytest.fixture(autouse=True)
def db_session() -> Generator[None, None, None]:
    """Isola cada teste em uma transação revertida e mocka o ChirpStack."""
    connection = engine.connect()
    transaction = connection.begin()

    def override_get_db() -> Generator[Session, None, None]:
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            session.close()

    def override_chirpstack() -> FakeChirpStackClient:
        return FakeChirpStackClient()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_chirpstack_client] = override_chirpstack
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_chirpstack_client, None)
    transaction.rollback()
    connection.close()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/tenant/"),
        ("get", "/api/v1/tenant"),
        ("get", "/api/v1/tenant/{tenant_id}"),
        ("patch", "/api/v1/tenant/{tenant_id}"),
        ("delete", "/api/v1/tenant/{tenant_id}"),
        ("post", "/api/v1/tenant/{tenant_id}/applications"),
        ("get", "/api/v1/tenant/{tenant_id}/applications"),
        ("get", "/api/v1/tenant/{tenant_id}/applications/{app_id}"),
        ("patch", "/api/v1/tenant/{tenant_id}/applications/{app_id}"),
        ("delete", "/api/v1/tenant/{tenant_id}/applications/{app_id}"),
        ("get", "/api/v1/devices"),
        ("post", "/api/v1/devices"),
        ("patch", "/api/v1/devices/{device_id}"),
        ("delete", "/api/v1/devices/{device_id}"),
        ("get", "/api/v1/device-profile/"),
        ("post", "/api/v1/user"),
        ("get", "/api/v1/user"),
        ("get", "/api/v1/user/{user_id}"),
        ("patch", "/api/v1/user/{user_id}"),
        ("delete", "/api/v1/user/{user_id}"),
    ],
)
def test_protected_route_without_token_returns_401(method, path):
    url = path.format(
        tenant_id=uuid4(),
        app_id=uuid4(),
        device_id=uuid4(),
        user_id=uuid4(),
    )
    params = {"app_id": uuid4()} if path == "/api/v1/devices" else None
    kwargs: dict = {}
    if method in {"post", "patch"}:
        kwargs["json"] = {}

    response = getattr(client, method)(url, params=params, **kwargs)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid service token"}


def test_protected_route_with_unconfigured_token_returns_503(monkeypatch):
    monkeypatch.setattr(shared_settings, "service_token", "")

    response = auth_client.get("/api/v1/tenant")

    assert response.status_code == 503


def test_tenant_list_with_service_token_returns_200():
    response = auth_client.get("/api/v1/tenant")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_user_list_with_service_token_returns_200():
    response = auth_client.get("/api/v1/user")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_device_profile_with_service_token_reaches_handler():
    response = auth_client.get(
        "/api/v1/device-profile/", params={"app_id": uuid4()}
    )

    assert response.status_code == 404


def test_health_stays_public():
    response = client.get("/health")

    assert response.status_code == 200
