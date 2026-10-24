from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from linx_shared.db.base import engine, get_db
from sqlalchemy.orm import Session

from identity_api.dependencies import (
    get_chirpstack_client,
    get_provisioner_client,
)
from identity_api.main import app
from identity_api.provisioner_client import (
    ProvisionedApplication,
    ProvisionerClientError,
)
from tests.auth import AUTH
from tests.fakes import FakeChirpStackClient

client = TestClient(app, headers=AUTH)


class FakeProvisionerClient:
    """Substitui o cliente gRPC nos testes HTTP do endpoint."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.created = True
        self.error: ProvisionerClientError | None = None

    def provision(self, app_id: str) -> ProvisionedApplication:
        self.calls.append(app_id)
        if self.error is not None:
            raise self.error
        return ProvisionedApplication(
            container_id="container-1",
            port=8200,
            network=f"linx-app-{app_id}",
            image="linx-tenant-app:latest",
            status="running",
            created=self.created,
            mqtt_topic=f"application/{app_id}/device/+/event/up",
        )

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def provisioner() -> Generator[FakeProvisionerClient, None, None]:
    fake = FakeProvisionerClient()

    def override() -> FakeProvisionerClient:
        return fake

    app.dependency_overrides[get_provisioner_client] = override
    yield fake
    app.dependency_overrides.pop(get_provisioner_client, None)


@pytest.fixture(autouse=True)
def chirpstack() -> Generator[FakeChirpStackClient, None, None]:
    """Isola o banco em uma transação revertida e mocka o ChirpStack."""
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

    fake = FakeChirpStackClient()

    def override_chirpstack() -> FakeChirpStackClient:
        return fake

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_chirpstack_client] = override_chirpstack
    yield fake
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_chirpstack_client, None)
    transaction.rollback()
    connection.close()


def _create_tenant(name: str = "Tenant Provision") -> str:
    response = client.post(
        "/api/v1/tenant/",
        json={"name": name, "description": "Descrição do teste"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_application(tenant_id: str, name: str = "App Provision") -> str:
    response = client.post(
        f"/api/v1/tenant/{tenant_id}/applications",
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _provision_url(tenant_id: str, app_id: str) -> str:
    return f"/api/v1/tenant/{tenant_id}/applications/{app_id}/provision"


def test_provision_returns_201_and_public_fields():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(_provision_url(tenant_id, app_id))

    assert response.status_code == 201
    data = response.json()
    assert data == {
        "container_id": "container-1",
        "port": 8200,
        "network": f"linx-app-{app_id}",
        "image": "linx-tenant-app:latest",
        "status": "running",
        "created": True,
        "mqtt_topic": f"application/{app_id}/device/+/event/up",
    }
    assert "db_password" not in data


def test_provision_returns_200_when_container_already_exists(provisioner):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    provisioner.created = False

    response = client.post(_provision_url(tenant_id, app_id))

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert provisioner.calls == [app_id]


def test_provision_unknown_tenant_returns_404():
    response = client.post(_provision_url(str(uuid4()), str(uuid4())))

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_provision_unknown_application_returns_404():
    tenant_id = _create_tenant()

    response = client.post(_provision_url(tenant_id, str(uuid4())))

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_provision_application_from_other_tenant_returns_404():
    tenant_one = _create_tenant("Tenant Um")
    tenant_two = _create_tenant("Tenant Dois")
    app_id = _create_application(tenant_one)

    response = client.post(_provision_url(tenant_two, app_id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_provision_requires_service_token():
    anonymous = TestClient(app)
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = anonymous.post(_provision_url(tenant_id, app_id))

    assert response.status_code == 401


@pytest.mark.parametrize("http_status", [409, 502, 503, 504])
def test_provision_maps_provisioner_errors(provisioner, http_status):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    provisioner.error = ProvisionerClientError(
        "provisioner falhou",
        status_code=http_status,
    )

    response = client.post(_provision_url(tenant_id, app_id))

    assert response.status_code == http_status
    assert response.json() == {"detail": "provisioner falhou"}
