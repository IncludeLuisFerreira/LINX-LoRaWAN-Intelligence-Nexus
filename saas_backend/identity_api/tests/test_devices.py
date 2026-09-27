from collections.abc import Generator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from chirpstack_api import api
from fastapi.testclient import TestClient
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import engine, get_db
from linx_shared.models.device import Device
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from identity_api.config import settings
from identity_api.main import app
from identity_api.routes.devices import get_chirpstack_client

client = TestClient(app)


class FakeChirpStackClient:
    def __init__(self) -> None:
        self.created: list[api.Device] = []
        self.deleted: list[str] = []
        self.created_keys: list[tuple[str, str]] = []
        self.error: ExternalServiceError | None = None
        self.keys_error: ExternalServiceError | None = None

    def create_device(self, device: api.Device) -> None:
        if self.error is not None:
            raise self.error
        self.created.append(device)

    def create_device_keys(self, dev_eui: str, app_key: str) -> None:
        if self.keys_error is not None:
            raise self.keys_error
        self.created_keys.append((dev_eui, app_key))

    def delete_device(self, dev_eui: str) -> None:
        if self.error is not None:
            raise self.error
        self.deleted.append(dev_eui)


@dataclass
class DeviceContext:
    chirpstack: FakeChirpStackClient
    connection: Connection

    @property
    def created(self) -> list[api.Device]:
        return self.chirpstack.created

    @property
    def deleted(self) -> list[str]:
        return self.chirpstack.deleted

    @property
    def created_keys(self) -> list[tuple[str, str]]:
        return self.chirpstack.created_keys

    @property
    def error(self) -> ExternalServiceError | None:
        return self.chirpstack.error

    @error.setter
    def error(self, value: ExternalServiceError | None) -> None:
        self.chirpstack.error = value

    @property
    def keys_error(self) -> ExternalServiceError | None:
        return self.chirpstack.keys_error

    @keys_error.setter
    def keys_error(self, value: ExternalServiceError | None) -> None:
        self.chirpstack.keys_error = value

    def count_devices(self) -> int:
        session = Session(
            bind=self.connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            return session.query(Device).count()
        finally:
            session.close()


@pytest.fixture(autouse=True)
def chirpstack(monkeypatch) -> Generator[DeviceContext, None, None]:
    """Isola o banco em uma transação revertida e mocka o ChirpStack."""
    monkeypatch.setattr(
        settings,
        "chirpstack_device_profile_id",
        "11111111-1111-1111-1111-111111111111",
    )
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
    yield DeviceContext(chirpstack=fake, connection=connection)
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


def _create_application(tenant_id: str, name: str = "Fazenda") -> str:
    response = client.post(
        f"/api/v1/tenant/{tenant_id}/applications", json={"name": name}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _payload(app_id: str, dev_eui: str = "1122334455667788") -> dict:
    return {
        "dev_eui": dev_eui,
        "app_id": app_id,
        "join_eui": "0011223344556677",
        "app_key": "00112233445566778899aabbccddeeff",
    }


def test_create_device_returns_201_with_full_body(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 201
    data = response.json()
    assert data["dev_eui"] == "1122334455667788"
    assert data["app_id"] == app_id
    assert data["join_eui"] == "0011223344556677"
    assert data["id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None
    assert "app_key" not in data


def test_create_device_provisions_in_chirpstack(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    client.post("/api/v1/devices", json=_payload(app_id))

    assert len(chirpstack.created) == 1
    device = chirpstack.created[0]
    assert device.dev_eui == "1122334455667788"
    assert device.application_id == app_id
    assert device.join_eui == "0011223344556677"
    assert device.name == "device-1122334455667788"


def test_create_device_normalizes_hex_to_lowercase(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(
        "/api/v1/devices",
        json=_payload(app_id, dev_eui="AABBCCDDEEFF0011"),
    )

    assert response.status_code == 201
    assert response.json()["dev_eui"] == "aabbccddeeff0011"
    assert chirpstack.created[0].dev_eui == "aabbccddeeff0011"


def test_create_device_in_non_existent_app_returns_404(chirpstack):
    fake_id = uuid4()

    response = client.post("/api/v1/devices", json=_payload(str(fake_id)))

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}
    assert chirpstack.created == []


def test_create_device_duplicate_dev_eui_returns_409(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    first = client.post("/api/v1/devices", json=_payload(app_id))
    assert first.status_code == 201

    second = client.post("/api/v1/devices", json=_payload(app_id))

    assert second.status_code == 409
    assert second.json() == {"detail": "Device already exists!"}
    assert len(chirpstack.created) == 1


def test_create_device_invalid_dev_eui_returns_422(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(
        "/api/v1/devices",
        json=_payload(app_id, dev_eui="zzzzzzzzzzzzzzzz"),
    )

    assert response.status_code == 422


def test_create_device_chirpstack_failure_returns_502_and_does_not_save(
    chirpstack,
):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    chirpstack.error = ExternalServiceError(
        "chirpstack", "create_device", "boom"
    )

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to provision device in ChirpStack: boom"
    }
    assert chirpstack.count_devices() == 0


def test_create_device_provisions_keys_in_chirpstack(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    client.post("/api/v1/devices", json=_payload(app_id))

    assert chirpstack.created_keys == [
        ("1122334455667788", "00112233445566778899aabbccddeeff")
    ]


def test_create_device_keys_failure_compensates_and_returns_502(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    chirpstack.keys_error = ExternalServiceError(
        "chirpstack", "create_device_keys", "boom"
    )

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to provision device in ChirpStack: boom"
    }
    assert chirpstack.deleted == ["1122334455667788"]
    assert chirpstack.count_devices() == 0


def test_create_device_missing_device_profile_returns_500(
    chirpstack, monkeypatch
):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    monkeypatch.setattr(settings, "chirpstack_device_profile_id", "")

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 500
    assert response.json() == {
        "detail": "ChirpStack device profile is not configured!"
    }
    assert chirpstack.created == []
    assert chirpstack.count_devices() == 0


def test_list_devices_returns_only_devices_of_app(chirpstack):
    tenant_id = _create_tenant()
    app_one = _create_application(tenant_id, "App Um")
    app_two = _create_application(tenant_id, "App Dois")

    device_one = client.post("/api/v1/devices", json=_payload(app_one)).json()
    device_two = client.post(
        "/api/v1/devices", json=_payload(app_one, dev_eui="2233445566778899")
    ).json()
    client.post(
        "/api/v1/devices", json=_payload(app_two, dev_eui="3344556677889900")
    )

    response = client.get("/api/v1/devices", params={"app_id": app_one})

    assert response.status_code == 200
    data = response.json()
    devices_by_id = {device["id"]: device for device in data}
    assert device_one["id"] in devices_by_id
    assert device_two["id"] in devices_by_id
    assert len(data) == 2


def test_list_devices_in_empty_app_returns_empty_list(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.get("/api/v1/devices", params={"app_id": app_id})

    assert response.status_code == 200
    assert response.json() == []


def test_list_devices_in_non_existent_app_returns_404(chirpstack):
    fake_id = uuid4()

    response = client.get("/api/v1/devices", params={"app_id": str(fake_id)})

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}


def test_delete_device_removes_it_and_propagates_to_chirpstack(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()

    response = client.delete(f"/api/v1/devices/{created['id']}")

    assert response.status_code == 204
    assert chirpstack.deleted == ["1122334455667788"]

    listing = client.get("/api/v1/devices", params={"app_id": app_id})
    assert listing.json() == []


def test_delete_non_existent_device_returns_404(chirpstack):
    fake_id = uuid4()

    response = client.delete(f"/api/v1/devices/{fake_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found!"}
    assert chirpstack.deleted == []


def test_delete_device_chirpstack_failure_returns_502_and_does_not_remove(
    chirpstack,
):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()
    chirpstack.error = ExternalServiceError(
        "chirpstack", "delete_device", "boom"
    )

    response = client.delete(f"/api/v1/devices/{created['id']}")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to delete device in ChirpStack: boom"
    }
    assert chirpstack.count_devices() == 1
