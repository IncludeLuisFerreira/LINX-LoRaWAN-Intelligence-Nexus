from collections.abc import Generator
from datetime import datetime
from time import sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.core.rabbitmq import (
    derive_tenant_password,
    tenant_namespace_regex,
    tenant_user,
)
from linx_shared.db.base import engine, get_db
from linx_shared.schemas.application import ApplicationCreate
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.config import settings
from identity_api.dependencies import get_chirpstack_client
from identity_api.main import app
from identity_api.routes.application import create_application
from tests.auth import AUTH
from tests.fakes import FakeChirpStackClient

client = TestClient(app, headers=AUTH)


@pytest.fixture(autouse=True)
def chirpstack() -> Generator[FakeChirpStackClient, None, None]:
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


def _create_tenant(name: str = "Tenant Teste") -> str:
    response = client.post(
        "/api/v1/tenant/",
        json={"name": name, "description": "Descrição do teste"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _applications_url(tenant_id: str) -> str:
    return f"/api/v1/tenant/{tenant_id}/applications"


def test_create_application_returns_created_with_full_body():
    tenant_id = _create_tenant()
    payload = {"name": "Fazenda", "description": "App do teste"}

    response = client.post(_applications_url(tenant_id), json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Fazenda"
    assert data["description"] == "App do teste"
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert response.headers["Location"] == (
        f"/api/v1/tenant/{tenant_id}/applications/{data['id']}"
    )


def test_create_application_without_description_uses_empty_default():
    tenant_id = _create_tenant()

    response = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Fazenda"
    assert data["description"] == ""
    assert data["id"] is not None


def test_create_application_in_non_existent_tenant_returns_404():
    fake_id = uuid4()

    response = client.post(
        _applications_url(str(fake_id)), json={"name": "Fazenda"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_list_applications_returns_only_apps_of_tenant():
    tenant_one = _create_tenant("Tenant Um")
    tenant_two = _create_tenant("Tenant Dois")

    app_one = client.post(
        _applications_url(tenant_one), json={"name": "App Um"}
    ).json()
    app_two = client.post(
        _applications_url(tenant_one), json={"name": "App Dois"}
    ).json()
    client.post(
        _applications_url(tenant_two), json={"name": "App Outro Tenant"}
    )

    response = client.get(_applications_url(tenant_one))

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    apps_by_id = {app["id"]: app for app in data}
    assert app_one["id"] in apps_by_id
    assert app_two["id"] in apps_by_id
    assert len(data) == 2


def test_list_applications_in_non_existent_tenant_returns_404():
    fake_id = uuid4()

    response = client.get(_applications_url(str(fake_id)))

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_get_application_returns_application():
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()

    response = client.get(f"{_applications_url(tenant_id)}/{created['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Fazenda"
    assert data["id"] == created["id"]
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_get_non_existent_application_returns_404():
    tenant_id = _create_tenant()
    fake_id = uuid4()

    response = client.get(f"{_applications_url(tenant_id)}/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_get_application_in_non_existent_tenant_returns_404():
    fake_id = uuid4()

    response = client.get(f"{_applications_url(str(fake_id))}/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_get_application_of_another_tenant_returns_404():
    tenant_one = _create_tenant("Tenant Um")
    tenant_two = _create_tenant("Tenant Dois")

    created = client.post(
        _applications_url(tenant_one), json={"name": "Fazenda"}
    ).json()

    response = client.get(f"{_applications_url(tenant_two)}/{created['id']}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_patch_application_updates_updated_at():
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()
    updated_before = datetime.fromisoformat(created["updated_at"])

    payload = {"name": "Fazenda Updated"}

    sleep(0.01)
    response = client.patch(
        f"{_applications_url(tenant_id)}/{created['id']}", json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Fazenda Updated"
    assert data["description"] == ""
    assert data["id"] == created["id"]
    assert data["created_at"] == created["created_at"]

    updated_after = datetime.fromisoformat(data["updated_at"])
    assert updated_after > updated_before


def test_patch_non_existent_application_returns_404():
    tenant_id = _create_tenant()
    fake_id = uuid4()

    response = client.patch(
        f"{_applications_url(tenant_id)}/{fake_id}",
        json={"name": "Fazenda Updated"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_patch_application_in_non_existent_tenant_returns_404():
    fake_id = uuid4()

    response = client.patch(
        f"{_applications_url(str(fake_id))}/{fake_id}",
        json={"name": "Fazenda Updated"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_delete_application_removes_it():
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()

    response = client.delete(f"{_applications_url(tenant_id)}/{created['id']}")

    assert response.status_code == 204

    response_get = client.get(
        f"{_applications_url(tenant_id)}/{created['id']}"
    )

    assert response_get.status_code == 404


def test_delete_non_existent_application_returns_404():
    tenant_id = _create_tenant()
    fake_id = uuid4()

    response = client.delete(f"{_applications_url(tenant_id)}/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_delete_application_in_non_existent_tenant_returns_404():
    fake_id = uuid4()

    response = client.delete(f"{_applications_url(str(fake_id))}/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_create_application_provisions_in_chirpstack_and_uses_returned_id(
    chirpstack,
):
    tenant_id = _create_tenant()

    response = client.post(
        _applications_url(tenant_id),
        json={"name": "Fazenda", "description": "desc"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(chirpstack.applications) == 1
    created = chirpstack.applications[0]
    assert created["tenant_id"] == tenant_id
    assert created["name"] == "Fazenda"
    assert created["description"] == "desc"
    assert data["id"] == created["id"]


def test_update_application_propagates_to_chirpstack(chirpstack):
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()

    response = client.patch(
        f"{_applications_url(tenant_id)}/{created['id']}",
        json={"name": "Fazenda Nova"},
    )

    assert response.status_code == 200
    assert chirpstack.updated_applications == [
        (created["id"], "Fazenda Nova", "")
    ]


def test_delete_application_propagates_to_chirpstack(chirpstack):
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()

    response = client.delete(f"{_applications_url(tenant_id)}/{created['id']}")

    assert response.status_code == 204
    assert chirpstack.deleted_applications == [created["id"]]


def test_create_application_chirpstack_failure_returns_502(chirpstack):
    tenant_id = _create_tenant()
    chirpstack.application_error = ExternalServiceError(
        "chirpstack", "create_application", "boom"
    )

    response = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to create application in ChirpStack: boom"
    }


def test_update_application_chirpstack_failure_still_returns_200(chirpstack):
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()
    chirpstack.application_error = ExternalServiceError(
        "chirpstack", "update_application", "boom"
    )

    response = client.patch(
        f"{_applications_url(tenant_id)}/{created['id']}",
        json={"name": "Fazenda Nova"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Fazenda Nova"


def test_delete_application_chirpstack_failure_returns_502(chirpstack):
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()
    chirpstack.application_error = ExternalServiceError(
        "chirpstack", "delete_application", "boom"
    )

    response = client.delete(f"{_applications_url(tenant_id)}/{created['id']}")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to delete application in ChirpStack: boom"
    }
    assert (
        client.get(
            f"{_applications_url(tenant_id)}/{created['id']}"
        ).status_code
        == 200
    )


def test_create_application_persist_failure_compensates_in_chirpstack(
    chirpstack, rabbitmq
):
    class _StubDb:
        def get(self, model, pk):
            return SimpleNamespace(id=pk)

        def add(self, obj) -> None:
            return None

        def commit(self) -> None:
            raise SQLAlchemyError("boom")

        def rollback(self) -> None:
            return None

    tenant_id = uuid4()
    payload = ApplicationCreate(name="Fazenda", description="")

    with pytest.raises(HTTPException) as exc_info:
        create_application(
            tenant_id=tenant_id,
            payload=payload,
            response=Response(),
            db=_StubDb(),
            chirpstack=chirpstack,
            rabbitmq=rabbitmq,
        )

    assert exc_info.value.status_code == 500
    assert chirpstack.deleted_applications == [
        chirpstack.applications[0]["id"]
    ]
    assert rabbitmq.deleted_users == [
        f"tenant.{chirpstack.applications[0]['id']}"
    ]


def test_create_application_provisions_rabbitmq_tenant(rabbitmq):
    tenant_id = _create_tenant()

    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()

    app_id = created["id"]
    user = tenant_user(app_id)
    assert user in rabbitmq.users
    assert rabbitmq.users[user] == derive_tenant_password(
        app_id, settings.rabbitmq_tenant_secret
    )
    assert rabbitmq.permissions[user] == tenant_namespace_regex(app_id)


def test_create_application_rabbitmq_failure_returns_502_and_compensates(
    chirpstack, rabbitmq
):
    tenant_id = _create_tenant()
    rabbitmq.error = ExternalServiceError("rabbitmq", "put_user", "boom")

    response = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to provision RabbitMQ tenant: boom"
    }
    assert len(chirpstack.applications) == 1
    assert chirpstack.deleted_applications == [
        chirpstack.applications[0]["id"]
    ]
    assert client.get(_applications_url(tenant_id)).json() == []


def test_delete_application_removes_rabbitmq_user(rabbitmq):
    tenant_id = _create_tenant()
    created = client.post(
        _applications_url(tenant_id), json={"name": "Fazenda"}
    ).json()

    response = client.delete(f"{_applications_url(tenant_id)}/{created['id']}")

    assert response.status_code == 204
    assert rabbitmq.deleted_users == [tenant_user(created["id"])]
