from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from time import sleep
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from linx.db.base import engine, get_db
from linx.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _rollback_db_transactions() -> Generator[None, None, None]:
    """Isola cada teste em uma transação revertida ao final.

    As requisições passam a usar uma sessão ligada a uma transação externa
    (via savepoint). Ao fim do teste a transação é revertida, então nenhum
    registro é persistido no banco real.
    """
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

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
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
