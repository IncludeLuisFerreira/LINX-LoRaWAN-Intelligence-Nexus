import grpc
from chirpstack_api import api
from linx_shared.core.exceptions import ExternalServiceError


class ChirpStackClient:
    def __init__(
        self,
        host: str,
        token: str,
        channel: grpc.Channel | None = None,
        use_tls: bool = False,
        ca_cert: str | None = None,
    ):
        self._host = host
        self._token = token
        if channel is not None:
            self._channel = channel
        elif use_tls:
            root_certificates = None
            if ca_cert:
                with open(ca_cert, "rb") as cert_file:
                    root_certificates = cert_file.read()
            credentials = grpc.ssl_channel_credentials(
                root_certificates=root_certificates
            )
            self._channel = grpc.secure_channel(host, credentials)
        else:
            self._channel = grpc.insecure_channel(host)

    def _metadata(self) -> list[tuple[str, str]]:
        return [("authorization", f"Bearer {self._token}")]

    def create_device(self, device: api.Device) -> None:
        stub = api.DeviceServiceStub(self._channel)
        request = api.CreateDeviceRequest(device=device)
        try:
            stub.Create(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="create_device",
                message=str(exc.details()),
                original_error=exc,
            ) from exc

    def delete_device(self, dev_eui: str) -> None:
        stub = api.DeviceServiceStub(self._channel)
        request = api.DeleteDeviceRequest(dev_eui=dev_eui)
        try:
            stub.Delete(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="delete_device",
                message=str(exc.details()),
                original_error=exc,
            ) from exc

    def create_device_keys(self, dev_eui: str, app_key: str) -> None:
        stub = api.DeviceServiceStub(self._channel)
        request = api.CreateDeviceKeysRequest(
            device_keys=api.DeviceKeys(
                dev_eui=dev_eui, nwk_key=app_key, app_key=app_key
            )
        )
        try:
            stub.CreateKeys(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="create_device_keys",
                message=str(exc.details()),
                original_error=exc,
            ) from exc

    def list_device_profiles(
        self, tenant_id: str
    ) -> list[api.DeviceProfileListItem]:
        stub = api.DeviceProfileServiceStub(self._channel)
        try:
            first = stub.List(
                api.ListDeviceProfilesRequest(tenant_id=tenant_id, limit=1),
                metadata=self._metadata(),
            )
            total = first.total_count
            if total == 0:
                return []
            response = stub.List(
                api.ListDeviceProfilesRequest(
                    tenant_id=tenant_id, limit=total
                ),
                metadata=self._metadata(),
            )
            return list(response.result)
        except grpc.RpcError as grpce:
            raise ExternalServiceError(
                service="chirpstack",
                operation="list_device_profiles",
                message=str(grpce.details() or grpce),
                original_error=grpce,
            ) from grpce

    def create_tenant(self, name: str, description: str) -> str:
        stub = api.TenantServiceStub(self._channel)
        request = api.CreateTenantRequest(
            tenant=api.Tenant(name=name, description=description)
        )
        try:
            response = stub.Create(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="create_tenant",
                message=str(exc.details() or exc),
                original_error=exc,
            ) from exc
        return response.id

    def update_tenant(
        self, tenant_id: str, name: str, description: str
    ) -> None:
        stub = api.TenantServiceStub(self._channel)
        request = api.UpdateTenantRequest(
            tenant=api.Tenant(id=tenant_id, name=name, description=description)
        )
        try:
            stub.Update(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="update_tenant",
                message=str(exc.details() or exc),
                original_error=exc,
            ) from exc

    def delete_tenant(self, tenant_id: str) -> None:
        stub = api.TenantServiceStub(self._channel)
        request = api.DeleteTenantRequest(id=tenant_id)
        try:
            stub.Delete(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="delete_tenant",
                message=str(exc.details() or exc),
                original_error=exc,
            ) from exc

    def create_application(
        self, tenant_id: str, name: str, description: str
    ) -> str:
        stub = api.ApplicationServiceStub(self._channel)
        request = api.CreateApplicationRequest(
            application=api.Application(
                tenant_id=tenant_id, name=name, description=description
            )
        )
        try:
            response = stub.Create(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="create_application",
                message=str(exc.details() or exc),
                original_error=exc,
            ) from exc
        return response.id

    def update_application(
        self, application_id: str, name: str, description: str
    ) -> None:
        stub = api.ApplicationServiceStub(self._channel)
        request = api.UpdateApplicationRequest(
            application=api.Application(
                id=application_id, name=name, description=description
            )
        )
        try:
            stub.Update(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="update_application",
                message=str(exc.details() or exc),
                original_error=exc,
            ) from exc

    def delete_application(self, application_id: str) -> None:
        stub = api.ApplicationServiceStub(self._channel)
        request = api.DeleteApplicationRequest(id=application_id)
        try:
            stub.Delete(request, metadata=self._metadata())
        except grpc.RpcError as exc:
            raise ExternalServiceError(
                service="chirpstack",
                operation="delete_application",
                message=str(exc.details() or exc),
                original_error=exc,
            ) from exc

    def close(self) -> None:
        self._channel.close()
