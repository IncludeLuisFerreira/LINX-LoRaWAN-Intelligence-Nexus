from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from linx_shared.models.application_instance import ApplicationInstance

from identity_api.dependencies import get_chirpstack_client
from identity_api.main import app
from tests.auth import AUTH
from tests.fakes import FakeChirpStackClient

client = TestClient(app, headers=AUTH)


@pytest.fixture(autouse=True)
def _isolated_db(db_session) -> Generator[None, None, None]:
    yield


@pytest.fixture(autouse=True)
def chirpstack() -> Generator[FakeChirpStackClient, None, None]:
    fake = FakeChirpStackClient()

    def override_chirpstack() -> FakeChirpStackClient:
        return fake

    app.dependency_overrides[get_chirpstack_client] = override_chirpstack
    yield fake
    app.dependency_overrides.pop(get_chirpstack_client, None)


def _create_tenant(name: str = "Tenant Status") -> str:
    response = client.post(
        "/api/v1/tenant/",
        json={"name": name, "description": "Descrição do teste"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_application(tenant_id: str, name: str = "App Status") -> str:
    response = client.post(
        f"/api/v1/tenant/{tenant_id}/applications",
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _status_url(tenant_id: str, app_id: str) -> str:
    return f"/api/v1/tenant/{tenant_id}/applications/{app_id}/status"


def _set_instance(db_session, app_id: str, **values) -> None:
    instance = (
        db_session.query(ApplicationInstance)
        .filter(ApplicationInstance.app_id == UUID(app_id))
        .one()
    )
    for key, value in values.items():
        setattr(instance, key, value)
    db_session.commit()


def test_status_returns_pending_for_new_instance():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.get(_status_url(tenant_id, app_id))

    assert response.status_code == 200
    body = response.json()
    assert body["app_id"] == app_id
    assert body["status"] == "PENDING"


def test_status_returns_provisioning(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    _set_instance(db_session, app_id, status="PROVISIONING")

    response = client.get(_status_url(tenant_id, app_id))

    assert response.status_code == 200
    body = response.json()
    assert body["app_id"] == app_id
    assert body["status"] == "PROVISIONING"


def test_status_returns_running_with_metadata(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    provisioned_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    _set_instance(
        db_session,
        app_id,
        status="RUNNING",
        container_id="abc123def456",
        port=8080,
        provisioned_at=provisioned_at,
    )

    response = client.get(_status_url(tenant_id, app_id))

    assert response.status_code == 200
    body = response.json()
    assert body["app_id"] == app_id
    assert body["status"] == "RUNNING"
    assert body["container_id"] == "abc123def456"
    assert body["port"] == 8080
    assert body["provisioned_at"].startswith("2026-01-02T03:04:05")


def test_status_returns_error(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    _set_instance(db_session, app_id, status="ERROR")

    response = client.get(_status_url(tenant_id, app_id))

    assert response.status_code == 200
    assert response.json()["status"] == "ERROR"


def test_status_unknown_application_returns_404():
    tenant_id = _create_tenant()

    response = client.get(_status_url(tenant_id, str(uuid4())))

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_status_missing_instance_returns_404(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    instance = (
        db_session.query(ApplicationInstance)
        .filter(ApplicationInstance.app_id == UUID(app_id))
        .one()
    )
    db_session.delete(instance)
    db_session.commit()

    response = client.get(_status_url(tenant_id, app_id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Application instance not found!"}


def test_status_cross_tenant_returns_404(db_session):
    """Aplicação de um tenant não pode ser lida por outro tenant (RF-013).

    O leak da tentativa 1 expunha `container_id`/`port` de qualquer aplicação
    ao enumerar UUIDs. Com o escopo por tenant, requisitar a aplicação do
    tenant A sob o tenant B devolve 404, sem revelar os metadados de A.
    """
    tenant_a = _create_tenant("Tenant A")
    app_a = _create_application(tenant_a, "App A")
    _set_instance(
        db_session,
        app_a,
        status="RUNNING",
        container_id="segredo-container-A",
        port=9999,
        provisioned_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    tenant_b = _create_tenant("Tenant B")

    leaked = client.get(_status_url(tenant_b, app_a))
    allowed = client.get(_status_url(tenant_a, app_a))

    assert leaked.status_code == 404
    assert leaked.json() == {"detail": "Application not found!"}
    assert "segredo-container-A" not in leaked.text
    assert "9999" not in leaked.text

    assert allowed.status_code == 200
    assert allowed.json()["container_id"] == "segredo-container-A"
    assert allowed.json()["port"] == 9999


def test_status_unknown_tenant_returns_404():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.get(_status_url(str(uuid4()), app_id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_status_requires_service_token():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    anonymous = TestClient(app)

    response = anonymous.get(_status_url(tenant_id, app_id))

    assert response.status_code == 401
