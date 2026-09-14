from collections.abc import Generator
from datetime import datetime
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
