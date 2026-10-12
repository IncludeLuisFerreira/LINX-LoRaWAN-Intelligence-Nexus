from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from time import sleep
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import engine, get_db
from linx_shared.schemas.tenant import TenantCreate
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.dependencies import get_chirpstack_client
from identity_api.main import app
from identity_api.routes.tenant import create_tenant
from tests.fakes import FakeChirpStackClient

client = TestClient(app)


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


def test_create_tenant_returns_created_with_full_body():
    payload = {
        "name": "Tenant Teste",
        "description": "Descrição do teste",
    }
    response = client.post("/api/v1/tenant/", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Tenant Teste"
    assert data["description"] == "Descrição do teste"
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert (
        response.headers["Location"]
        == f"http://testserver/api/v1/tenant/{data['id']}"
    )


def test_create_tenant_without_description_uses_empty_default():
    response = client.post("/api/v1/tenant/", json={"name": "Tenant ACME"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Tenant ACME"
    assert data["description"] == ""
    assert data["id"] is not None


def test_created_at_is_generated_per_insert():
    first = client.post(
        "/api/v1/tenant/", json={"name": "Tenant Primeiro"}
    ).json()
    second = client.post(
        "/api/v1/tenant/", json={"name": "Tenant Segundo"}
    ).json()

    first_created = datetime.fromisoformat(first["created_at"])
    second_created = datetime.fromisoformat(second["created_at"])
    now = datetime.now(timezone.utc)

    assert first_created != second_created
    assert now - timedelta(minutes=5) <= first_created <= now
    assert now - timedelta(minutes=5) <= second_created <= now


def test_list_tenants_return_all_created_tenants():
    payload_one = {
        "name": "Tenant Lista Um",
        "description": "Descrição do primeiro tenant",
    }
    payload_two = {
        "name": "Tenant Lista Dois",
        "description": "Descrição do segundo tenant",
    }

    created_one = client.post("/api/v1/tenant/", json=payload_one).json()
    created_two = client.post("/api/v1/tenant/", json=payload_two).json()

    response = client.get("/api/v1/tenant")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    tenants_by_id = {tenant["id"]: tenant for tenant in data}
    assert created_one["id"] in tenants_by_id
    assert created_two["id"] in tenants_by_id
    assert tenants_by_id[created_one["id"]]["name"] == "Tenant Lista Um"
    assert tenants_by_id[created_two["id"]]["name"] == "Tenant Lista Dois"


def test_get_tenant_return_tenant_desc():
    payload = {
        "name": "Tenant Teste",
        "description": "Descrição do teste",
    }
    data_post = client.post("/api/v1/tenant/", json=payload).json()

    response = client.get(f"/api/v1/tenant/{data_post['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tenant Teste"
    assert data["description"] == "Descrição do teste"
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_get_non_existent_tenant_return_404():
    fake_id = uuid4()
    response = client.get(f"/api/v1/tenant/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_patch_tenant_updates_updated_at():
    payload = {
        "name": "Tenant Teste",
        "description": "Descrição do teste",
    }
    response_post = client.post("/api/v1/tenant/", json=payload)

    assert response_post.status_code == 201
    data_post = response_post.json()
    updated_before = datetime.fromisoformat(data_post["updated_at"])

    payload_updated = {
        "name": "Tenant Updated",
        "description": "Descrição do Update teste",
    }

    sleep(0.01)
    response = client.patch(
        f"/api/v1/tenant/{data_post['id']}", json=payload_updated
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tenant Updated"
    assert data["description"] == "Descrição do Update teste"
    assert data["id"] == data_post["id"]
    assert data["created_at"] == data_post["created_at"]

    updated_after = datetime.fromisoformat(data["updated_at"])
    assert updated_after > updated_before


def test_uppate_non_existent_tenant_return_404():
    payload_updated = {
        "name": "Tenant não existente Updated",
        "description": "Descrição do Update teste de um tenant não existente",
    }

    fake_id = uuid4()
    response = client.patch(f"/api/v1/tenant/{fake_id}", json=payload_updated)

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_delete_tenant_return_successfully():
    payload = {
        "name": "Tenant Teste",
        "description": "Descrição do teste",
    }
    response_post = client.post("/api/v1/tenant/", json=payload)

    assert response_post.status_code == 201
    data_post = response_post.json()

    response = client.delete(f"/api/v1/tenant/{data_post['id']}")

    assert response.status_code == 204

    response_get = client.get(f"/api/v1/tenant/{data_post['id']}")

    assert response_get.status_code == 404


def test_delete_non_existent_tenant_return_404():
    fake_id = uuid4()
    response = client.delete(f"/api/v1/tenant/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_create_tenant_provisions_in_chirpstack_and_uses_returned_id(
    chirpstack,
):
    response = client.post(
        "/api/v1/tenant/",
        json={"name": "Tenant Provisionado", "description": "desc"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(chirpstack.tenants) == 1
    created = chirpstack.tenants[0]
    assert created["name"] == "Tenant Provisionado"
    assert created["description"] == "desc"
    assert data["id"] == created["id"]


def test_update_tenant_propagates_to_chirpstack(chirpstack):
    created = client.post("/api/v1/tenant/", json={"name": "Tenant"}).json()

    response = client.patch(
        f"/api/v1/tenant/{created['id']}", json={"name": "Tenant Novo"}
    )

    assert response.status_code == 200
    assert chirpstack.updated_tenants == [(created["id"], "Tenant Novo", "")]


def test_delete_tenant_propagates_to_chirpstack(chirpstack):
    created = client.post("/api/v1/tenant/", json={"name": "Tenant"}).json()

    response = client.delete(f"/api/v1/tenant/{created['id']}")

    assert response.status_code == 204
    assert chirpstack.deleted_tenants == [created["id"]]


def test_create_tenant_chirpstack_failure_returns_502(chirpstack):
    chirpstack.tenant_error = ExternalServiceError(
        "chirpstack", "create_tenant", "boom"
    )

    response = client.post("/api/v1/tenant/", json={"name": "Tenant"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to create tenant in ChirpStack: boom"
    }


def test_update_tenant_chirpstack_failure_still_returns_200(chirpstack):
    created = client.post("/api/v1/tenant/", json={"name": "Tenant"}).json()
    chirpstack.tenant_error = ExternalServiceError(
        "chirpstack", "update_tenant", "boom"
    )

    response = client.patch(
        f"/api/v1/tenant/{created['id']}", json={"name": "Tenant Novo"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Tenant Novo"


def test_delete_tenant_chirpstack_failure_returns_502(chirpstack):
    created = client.post("/api/v1/tenant/", json={"name": "Tenant"}).json()
    chirpstack.tenant_error = ExternalServiceError(
        "chirpstack", "delete_tenant", "boom"
    )

    response = client.delete(f"/api/v1/tenant/{created['id']}")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to delete tenant in ChirpStack: boom"
    }
    assert client.get(f"/api/v1/tenant/{created['id']}").status_code == 200


def test_create_tenant_persist_failure_compensates_in_chirpstack(chirpstack):
    class _StubDb:
        def add(self, obj) -> None:
            return None

        def commit(self) -> None:
            raise SQLAlchemyError("boom")

        def rollback(self) -> None:
            return None

    payload = TenantCreate(name="Tenant", description="")

    with pytest.raises(HTTPException) as exc_info:
        create_tenant(
            payload=payload,
            request=None,
            response=Response(),
            db=_StubDb(),
            chirpstack=chirpstack,
        )

    assert exc_info.value.status_code == 500
    assert chirpstack.deleted_tenants == [chirpstack.tenants[0]["id"]]
