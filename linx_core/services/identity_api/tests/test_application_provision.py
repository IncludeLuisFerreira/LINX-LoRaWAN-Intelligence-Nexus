from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from linx_shared.models.job_outbox import JobOutbox
from sqlalchemy.orm import Session

from identity_api.dependencies import get_chirpstack_client
from identity_api.main import app
from tests.auth import AUTH
from tests.fakes import FakeChirpStackClient

client = TestClient(app, headers=AUTH)


@pytest.fixture(autouse=True)
def _isolated_db(db_session: Session) -> Generator[None, None, None]:
    """Garante a transação isolada compartilhada com os testes."""
    yield


@pytest.fixture(autouse=True)
def chirpstack() -> Generator[FakeChirpStackClient, None, None]:
    fake = FakeChirpStackClient()

    def override_chirpstack() -> FakeChirpStackClient:
        return fake

    app.dependency_overrides[get_chirpstack_client] = override_chirpstack
    yield fake
    app.dependency_overrides.pop(get_chirpstack_client, None)


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


def _job_url(tenant_id: str, job_id: str) -> str:
    return f"/api/v1/tenant/{tenant_id}/jobs/{job_id}"


def test_provision_returns_202_with_pending_job():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(_provision_url(tenant_id, app_id))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["application_id"] == app_id
    assert response.headers["Location"].endswith(
        f"/api/v1/tenant/{tenant_id}/jobs/{body['job_id']}"
    )


def test_duplicate_provision_returns_same_job():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    first = client.post(_provision_url(tenant_id, app_id))
    second = client.post(_provision_url(tenant_id, app_id))

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_provision_creates_one_outbox_row(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    client.post(_provision_url(tenant_id, app_id))

    rows = db_session.query(JobOutbox).all()
    assert len(rows) == 1
    assert rows[0].exchange == "linx.jobs"
    assert rows[0].routing_key == "provisioning.application.requested"
    assert rows[0].payload["type"] == "provisioning.application"


def test_provision_outbox_has_no_secrets(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    client.post(_provision_url(tenant_id, app_id))

    payload = db_session.query(JobOutbox).one().payload
    serialized = str(payload).lower()
    assert "service_token" not in serialized
    assert "db_password" not in serialized
    assert "password" not in serialized


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


def test_job_status_route_returns_pending_job():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    provision = client.post(_provision_url(tenant_id, app_id))
    job_id = provision.json()["job_id"]

    response = client.get(_job_url(tenant_id, job_id))

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "pending"
    assert body["type"] == "provisioning.application"
    assert body["subject_id"] == app_id


def test_job_status_route_unknown_job_returns_404():
    tenant_id = _create_tenant()

    response = client.get(_job_url(tenant_id, str(uuid4())))

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found!"}
