from linx_shared.clients.docker_provisioner import (
    DockerProvisionerClient as SharedDockerProvisionerClient,
)
from linx_shared.clients.docker_provisioner import (
    ProvisionedApplication,
    ProvisionerClientError,
)

from identity_api.config import settings


class DockerProvisionerClient(SharedDockerProvisionerClient):
    def __init__(
        self,
        *,
        target: str | None = None,
        service_token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            target=target or settings.provisioner_grpc_host,
            service_token=(
                settings.service_token
                if service_token is None
                else service_token
            ),
            timeout=(
                settings.provisioner_grpc_timeout_seconds
                if timeout is None
                else timeout
            ),
        )


__all__ = [
    "DockerProvisionerClient",
    "ProvisionedApplication",
    "ProvisionerClientError",
]
