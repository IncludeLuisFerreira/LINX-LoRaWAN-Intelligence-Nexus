from collections.abc import Generator
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from chirpstack_api import api
from fastapi import HTTPException
from fastapi.testclient import TestClient
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import engine, get_db
from linx_shared.models.device import Device
from linx_shared.schemas.device import DeviceCreate
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity_api import dependencies as deps_module
from identity_api.main import app
from identity_api.routes.devices import (
    create_device,
    get_chirpstack_client,
)
from tests.auth import AUTH
from tests.fakes import FakeChirpStackClient

client = TestClient(app, headers=AUTH)

PROFILE_ID = "11111111-1111-1111-1111-111111111111"


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
    def create_error(self) -> ExternalServiceError | None:
        return self.chirpstack.create_error

    @create_error.setter
    def create_error(self, value: ExternalServiceError | None) -> None:
        self.chirpstack.create_error = value

    @property
    def keys_error(self) -> ExternalServiceError | None:
        return self.chirpstack.keys_error

    @keys_error.setter
    def keys_error(self, value: ExternalServiceError | None) -> None:
        self.chirpstack.keys_error = value

    @property
    def profile_calls(self) -> list[str]:
        return self.chirpstack.profile_calls

    @property
    def profiles(self) -> list[api.DeviceProfileListItem]:
        return self.chirpstack.profiles

    @profiles.setter
    def profiles(self, value: list[api.DeviceProfileListItem]) -> None:
        self.chirpstack.profiles = value

    @property
    def profile_error(self) -> ExternalServiceError | None:
        return self.chirpstack.profile_error

    @profile_error.setter
    def profile_error(self, value: ExternalServiceError | None) -> None:
        self.chirpstack.profile_error = value

    def count_devices(self, app_id: UUID | None = None) -> int:
        session = Session(
            bind=self.connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            query = session.query(Device)
            if app_id is not None:
                query = query.filter(Device.app_id == app_id)
            return query.count()
        finally:
            session.close()


@pytest.fixture(autouse=True)
def chirpstack(monkeypatch) -> Generator[DeviceContext, None, None]:
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
    fake.profiles = [api.DeviceProfileListItem(id=PROFILE_ID, name="perfil")]

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


def _payload(app_id: str, dev_eui: str = "1122334455667788", **extra) -> dict:
    return {
        "dev_eui": dev_eui,
        "app_id": app_id,
        "join_eui": "0011223344556677",
        "app_key": "00112233445566778899aabbccddeeff",
        "device_profile_id": PROFILE_ID,
        **extra,
    }


def test_create_device_with_nickname(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="Sensor Galpão")
    )

    assert response.status_code == 201
    assert response.json()["nickname"] == "Sensor Galpão"


def test_create_device_without_nickname_is_null(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 201
    assert response.json()["nickname"] is None


def test_create_device_blank_nickname_becomes_null(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="   ")
    )

    assert response.status_code == 201
    assert response.json()["nickname"] is None


def test_create_device_returns_201_with_full_body(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 201
    data = response.json()
    assert data["dev_eui"] == "1122334455667788"
    assert data["app_id"] == app_id
    assert data["join_eui"] == "0011223344556677"
    assert data["device_profile_id"] == PROFILE_ID
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
    assert device.device_profile_id == PROFILE_ID
    assert device.name == "device-1122334455667788"
    assert chirpstack.profile_calls == [tenant_id]


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
    assert chirpstack.count_devices(UUID(app_id)) == 0


def test_create_device_create_failure_does_not_delete(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    chirpstack.create_error = ExternalServiceError(
        "chirpstack", "create_device", "boom"
    )

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to provision device in ChirpStack: boom"
    }
    assert chirpstack.deleted == []
    assert chirpstack.count_devices(UUID(app_id)) == 0


def test_create_device_commit_integrity_error_returns_409_without_delete():
    fake = FakeChirpStackClient()
    fake.profiles = [api.DeviceProfileListItem(id=PROFILE_ID, name="perfil")]
    app_id = uuid4()
    application = SimpleNamespace(id=app_id, tenant_id=uuid4())

    class _StubQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class _StubDb:
        def __init__(self) -> None:
            self.rolled_back = False

        def get(self, model, pk):
            return application

        def query(self, model):
            return _StubQuery()

        def add(self, obj) -> None:
            return None

        def commit(self) -> None:
            raise IntegrityError("stmt", {}, Exception("duplicate"))

        def rollback(self) -> None:
            self.rolled_back = True

    db = _StubDb()
    payload = DeviceCreate(
        dev_eui="1122334455667788",
        app_id=app_id,
        join_eui="0011223344556677",
        app_key="00112233445566778899aabbccddeeff",
        device_profile_id=UUID(PROFILE_ID),
    )

    with pytest.raises(HTTPException) as exc_info:
        create_device(payload=payload, db=db, chirpstack=fake)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Device already exists!"
    assert fake.deleted == []
    assert db.rolled_back is True


def test_get_chirpstack_client_returns_singleton(monkeypatch):
    deps_module._build_chirpstack_client.cache_clear()
    constructed: list[tuple] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            constructed.append((args, kwargs))

        def close(self) -> None:
            return None

    monkeypatch.setattr(deps_module, "ChirpStackClient", _FakeClient)
    try:
        first = deps_module.get_chirpstack_client()
        second = deps_module.get_chirpstack_client()

        assert first is second
        assert len(constructed) == 1
    finally:
        deps_module._build_chirpstack_client.cache_clear()


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
    assert chirpstack.count_devices(UUID(app_id)) == 0


def test_create_device_unknown_device_profile_returns_400(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    chirpstack.profiles = []

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Device profile not found for this tenant!"
    }
    assert chirpstack.created == []
    assert chirpstack.count_devices(UUID(app_id)) == 0


def test_create_device_profile_lookup_failure_returns_502(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    chirpstack.profile_error = ExternalServiceError(
        "chirpstack", "list_device_profiles", "boom"
    )

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Failed to validate device profile in ChirpStack: boom"
    }
    assert chirpstack.created == []
    assert chirpstack.count_devices(UUID(app_id)) == 0


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


def test_delete_device_removes_local_even_when_chirpstack_fails(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()
    chirpstack.error = ExternalServiceError(
        "chirpstack", "delete_device", "boom"
    )

    response = client.delete(f"/api/v1/devices/{created['id']}")

    assert response.status_code == 204
    assert chirpstack.count_devices(UUID(app_id)) == 0
    assert chirpstack.deleted == []


def test_update_device_nickname(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": "Bomba 1"}
    )

    assert response.status_code == 200
    assert response.json()["nickname"] == "Bomba 1"


def test_update_device_clears_nickname_with_null(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="Bomba 1")
    ).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": None}
    )

    assert response.status_code == 200
    assert response.json()["nickname"] is None


def test_update_device_without_nickname_leaves_it_unchanged(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="Bomba 1")
    ).json()

    response = client.patch(f"/api/v1/devices/{created['id']}", json={})

    assert response.status_code == 200
    assert response.json()["nickname"] == "Bomba 1"


def test_update_device_not_found_returns_404(chirpstack):
    response = client.patch(
        f"/api/v1/devices/{uuid4()}", json={"nickname": "x"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found!"}


def test_update_device_nickname_too_long_returns_422(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": "a" * 51}
    )

    assert response.status_code == 422


def test_update_device_nickname_strips_before_length_check(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": "  " + "a" * 50}
    )

    assert response.status_code == 200
    assert response.json()["nickname"] == "a" * 50
