import uuid

from fastapi.testclient import TestClient

from linx.main import app

client = TestClient(app)


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

    client.delete(f"/api/v1/tenant/{data['id']}")


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
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/tenant/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}


def test_patch_tenant_return_tenand_updated():
    payload = {
        "name": "Tenant Teste",
        "description": "Descrição do teste",
    }
    response_post = client.post("/api/v1/tenant/", json=payload)

    assert response_post.status_code == 201
    data_post = response_post.json()

    payload_updated = {
        "name": "Tenant Updated",
        "description": "Descrição do Update teste",
    }

    response = client.patch(
        f"/api/v1/tenant/{data_post['id']}", json=payload_updated
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tenant Updated"
    assert data["description"] == "Descrição do Update teste"
    assert data["id"] == data_post["id"]
    assert data["created_at"] == data_post["created_at"]
    assert data["updated_at"] is not None


def test_uppate_non_existent_tenant_return_404():
    payload_updated = {
        "name": "Tenant não existente Updated",
        "description": "Descrição do Update teste de um tenant não existente",
    }

    fake_id = uuid.uuid4()
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
    fake_id = uuid.uuid4()
    response = client.delete(f"/api/v1/tenant/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}