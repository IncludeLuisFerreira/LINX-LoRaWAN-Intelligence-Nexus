from collections.abc import Generator
from dataclasses import dataclass
from uuid import uuid4

import pytest
from chirpstack_api import api
from fastapi.testclient import TestClient
from linx_shared.core.exceptions import ExternalServiceError
from linx_shared.db.base import engine, get_db
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from identity_api.main import app
from identity_api.routes.device_profile import get_chirpstack_client

client = TestClient(app)


class FakeChirpStackClient:
    def __init__(self) -> None:
        self.list_calls: list[str] = []
        self.profiles: list[api.DeviceProfileListItem] = []
        self.error: ExternalServiceError | None = None

    def create_tenant(self, name: str, description: str) -> str:
        return str(uuid4())

    def create_application(
        self, tenant_id: str, name: str, description: str
    ) -> str:
        return str(uuid4())

    def list_device_profiles(
        self, tenant_id: str
    ) -> list[api.DeviceProfileListItem]:
        self.list_calls.append(tenant_id)
        if self.error is not None:
            raise self.error
        return self.profiles


@dataclass
class DeviceProfileContext:
    chirpstack: FakeChirpStackClient
    connection: Connection

    @property
    def list_calls(self) -> list[str]:
        return self.chirpstack.list_calls

    @property
    def profiles(self) -> list[api.DeviceProfileListItem]:
        return self.chirpstack.profiles

    @profiles.setter
    def profiles(self, value: list[api.DeviceProfileListItem]) -> None:
        self.chirpstack.profiles = value


@pytest.fixture(autouse=True)
def chirpstack(monkeypatch) -> Generator[DeviceProfileContext, None, None]:
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
    yield DeviceProfileContext(chirpstack=fake, connection=connection)
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


def test_list_device_profiles_returns_profiles_of_app_tenant(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    profile_one = uuid4()
    profile_two = uuid4()
    chirpstack.profiles = [
        api.DeviceProfileListItem(id=str(profile_one), name="profile-1"),
        api.DeviceProfileListItem(id=str(profile_two), name="profile-2"),
    ]

    response = client.get("/api/v1/device-profile/", params={"app_id": app_id})

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(profile_one), "name": "profile-1"},
        {"id": str(profile_two), "name": "profile-2"},
    ]
    assert chirpstack.list_calls == [tenant_id]


def test_list_device_profiles_non_existent_app_returns_404(chirpstack):
    fake_id = uuid4()

    response = client.get(
        "/api/v1/device-profile/", params={"app_id": str(fake_id)}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found!"}
    assert chirpstack.list_calls == []
