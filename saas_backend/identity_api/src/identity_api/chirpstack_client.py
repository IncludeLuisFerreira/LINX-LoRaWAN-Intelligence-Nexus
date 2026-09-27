import grpc
from chirpstack_api import api


class ChirpStackClient:
    def __init__(
        self, host: str, token: str, channel: grpc.Channel | None = None
    ):
        self.host = host
        self.token = token
        self._channel = channel or grpc.insecure_channel(host)

    def _metadata(self) -> list[tuple[str, str]]:
        return [("authorization", f"Bearer {self.token}")]

    def create_device(self, device: api.Device) -> None:
        stub = api.DeviceServiceStub(self._channel)
        request = api.CreateDeviceRequest(device=device)
        stub.Create(request, metadata=self._metadata())
