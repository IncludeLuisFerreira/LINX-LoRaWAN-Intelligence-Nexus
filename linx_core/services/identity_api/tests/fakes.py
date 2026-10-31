from uuid import uuid4

from chirpstack_api import api
from linx_shared.core.exceptions import ExternalServiceError


class FakeRabbitMQClient:
    def __init__(self) -> None:
        self.users: dict[str, str] = {}
        self.permissions: dict[str, str] = {}
        self.deleted_users: list[str] = []
        self.error: ExternalServiceError | None = None

    def put_user(self, user: str, password: str) -> None:
        if self.error is not None:
            raise self.error
        self.users[user] = password

    def set_permissions(self, user: str, regex: str) -> None:
        if self.error is not None:
            raise self.error
        self.permissions[user] = regex

    def delete_user(self, user: str) -> None:
        self.deleted_users.append(user)


class FakeChirpStackClient:
    def __init__(self) -> None:
        self.tenants: list[dict] = []
        self.updated_tenants: list[tuple[str, str, str]] = []
        self.deleted_tenants: list[str] = []
        self.applications: list[dict] = []
        self.updated_applications: list[tuple[str, str, str]] = []
        self.deleted_applications: list[str] = []
        self.created: list[api.Device] = []
        self.deleted: list[str] = []
        self.created_keys: list[tuple[str, str]] = []
        self.profile_calls: list[str] = []
        self.profiles: list[api.DeviceProfileListItem] = []
        self.error: ExternalServiceError | None = None
        self.create_error: ExternalServiceError | None = None
        self.keys_error: ExternalServiceError | None = None
        self.profile_error: ExternalServiceError | None = None
        self.tenant_error: ExternalServiceError | None = None
        self.application_error: ExternalServiceError | None = None

    def create_tenant(self, name: str, description: str) -> str:
        if self.tenant_error is not None:
            raise self.tenant_error
        new_id = str(uuid4())
        self.tenants.append(
            {"id": new_id, "name": name, "description": description}
        )
        return new_id

    def update_tenant(
        self, tenant_id: str, name: str, description: str
    ) -> None:
        if self.tenant_error is not None:
            raise self.tenant_error
        self.updated_tenants.append((tenant_id, name, description))

    def delete_tenant(self, tenant_id: str) -> None:
        if self.tenant_error is not None:
            raise self.tenant_error
        self.deleted_tenants.append(tenant_id)

    def create_application(
        self, tenant_id: str, name: str, description: str
    ) -> str:
        if self.application_error is not None:
            raise self.application_error
        new_id = str(uuid4())
        self.applications.append(
            {
                "id": new_id,
                "tenant_id": tenant_id,
                "name": name,
                "description": description,
            }
        )
        return new_id

    def update_application(
        self, application_id: str, name: str, description: str
    ) -> None:
        if self.application_error is not None:
            raise self.application_error
        self.updated_applications.append((application_id, name, description))

    def delete_application(self, application_id: str) -> None:
        if self.application_error is not None:
            raise self.application_error
        self.deleted_applications.append(application_id)

    def create_device(self, device: api.Device) -> None:
        if self.create_error is not None:
            raise self.create_error
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

    def list_device_profiles(
        self, tenant_id: str
    ) -> list[api.DeviceProfileListItem]:
        self.profile_calls.append(tenant_id)
        if self.profile_error is not None:
            raise self.profile_error
        return self.profiles
