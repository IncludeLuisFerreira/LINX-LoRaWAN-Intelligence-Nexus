import grpc
from chirpstack_api import api
from linx_shared.core.exceptions import ExternalServiceError


class ChirpStackClient:
    def __init__(
        self, host: str, token: str, channel: grpc.Channel | None = None
    ):
        self._host = host
        self._token = token
        self._channel = channel or grpc.insecure_channel(host)

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
            device_keys=api.DeviceKeys(dev_eui=dev_eui, nwk_key=app_key)
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

    def close(self) -> None:
        self._channel.close()
