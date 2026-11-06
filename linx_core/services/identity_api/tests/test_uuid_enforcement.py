from uuid import UUID, uuid1, uuid3, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient

from identity_api.main import app
from tests.auth import AUTH

client = TestClient(app, headers=AUTH)

_NAMESPACE = UUID("00000000-0000-0000-0000-000000000000")

NON_V4 = [
    uuid1(),
    uuid3(_NAMESPACE, "abc"),
    uuid5(_NAMESPACE, "abc"),
    UUID(int=0),
]
INVALID = ["not-a-uuid", "3f3b3", "12345"]


@pytest.mark.parametrize("value", NON_V4)
def test_path_param_rejects_non_v4_tenant(value: UUID) -> None:
    response = client.get(f"/api/v1/tenant/{value}")
    assert response.status_code == 422
    assert "version 4" in response.text.lower()


@pytest.mark.parametrize("value", NON_V4)
def test_path_param_rejects_non_v4_nested_application(
    value: UUID,
) -> None:
    response = client.get(f"/api/v1/tenant/{value}/applications")
    assert response.status_code == 422
    assert "version 4" in response.text.lower()


@pytest.mark.parametrize("value", NON_V4)
def test_query_param_rejects_non_v4_app_id(value: UUID) -> None:
    response = client.get("/api/v1/devices", params={"app_id": str(value)})
    assert response.status_code == 422


@pytest.mark.parametrize("value", INVALID)
def test_path_param_rejects_invalid_uuid(value: str) -> None:
    response = client.get(f"/api/v1/tenant/{value}")
    assert response.status_code == 422
    assert "uuid" in response.text.lower()


def test_body_field_rejects_non_v4_device_profile() -> None:
    payload = {
        "dev_eui": "1122334455667788",
        "app_id": str(uuid1()),
        "join_eui": "0011223344556677",
        "app_key": "00112233445566778899aabbccddeeff",
        "device_profile_id": str(uuid5(_NAMESPACE, "perfil")),
    }
    response = client.post("/api/v1/devices", json=payload)
    assert response.status_code == 422
    assert "version 4" in response.text.lower()


def test_valid_v4_tenant_id_is_accepted_by_validator(db_session) -> None:
    """Um tenant_id v4 válido passa pela validação e chega ao handler.

    Como o id aleatório não existe no banco, o handler responde 404 — o
    que comprova que o validador UUID4 aceitou o valor (não houve 422).
    """
    response = client.get(f"/api/v1/tenant/{uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Tenant not found!"}
