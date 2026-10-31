from __future__ import annotations

from dataclasses import dataclass

import grpc

from linx_shared.grpc import (
    linx_docker_provisioner_pb2,
    linx_docker_provisioner_pb2_grpc,
)

# Tradução dos status gRPC do provisioner para o contrato HTTP do endpoint.
# Códigos de configuração interna (auth/contrato) viram 502 para não expor
# detalhes do serviço; indisponibilidade e esgotamento viram 503.
_GRPC_TO_HTTP_STATUS = {
    grpc.StatusCode.UNAVAILABLE: 503,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
    grpc.StatusCode.RESOURCE_EXHAUSTED: 503,
    grpc.StatusCode.ABORTED: 409,
    grpc.StatusCode.UNAUTHENTICATED: 502,
    grpc.StatusCode.PERMISSION_DENIED: 502,
    grpc.StatusCode.INVALID_ARGUMENT: 502,
    grpc.StatusCode.FAILED_PRECONDITION: 502,
    grpc.StatusCode.INTERNAL: 502,
    grpc.StatusCode.UNKNOWN: 502,
}
_DEFAULT_HTTP_STATUS = 502


class ProvisionerClientError(RuntimeError):
    """Falha ao chamar o docker_provisioner, já traduzida para HTTP."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        grpc_code: grpc.StatusCode | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.grpc_code = grpc_code


@dataclass(frozen=True)
class ProvisionedApplication:
    """Dados públicos devolvidos pelo serviço de provisionamento."""

    container_id: str
    port: int
    network: str
    image: str
    status: str
    created: bool
    mqtt_topic: str


class DockerProvisionerClient:
    """Cliente gRPC compartilhado para provisionar containers."""

    def __init__(
        self,
        *,
        target: str,
        service_token: str,
        timeout: float,
    ) -> None:
        self._target = target
        self._service_token = service_token
        self._timeout = timeout
        self._channel = grpc.insecure_channel(self._target)
        self._stub = linx_docker_provisioner_pb2_grpc.DockerProvisionerStub(
            self._channel
        )

    def provision(self, app_id: str) -> ProvisionedApplication:
        """Chama o provisioner e converte a resposta para o domínio local."""
        if not self._service_token:
            raise ProvisionerClientError(
                "Service token is not configured",
                status_code=503,
            )

        request_cls = getattr(
            linx_docker_provisioner_pb2,
            "ProvisionApplicationRequest",
        )
        request = request_cls(app_id=app_id)
        metadata = (("authorization", f"Bearer {self._service_token}"),)

        try:
            response = self._stub.ProvisionApplication(
                request,
                metadata=metadata,
                timeout=self._timeout,
            )
        except grpc.RpcError as exc:
            status_code = _GRPC_TO_HTTP_STATUS.get(
                exc.code(), _DEFAULT_HTTP_STATUS
            )
            details = exc.details() or str(exc)
            raise ProvisionerClientError(
                f"Provisioner error: {details}",
                status_code=status_code,
                grpc_code=exc.code(),
            ) from exc

        return ProvisionedApplication(
            container_id=response.container_id,
            port=response.port,
            network=response.network,
            image=response.image,
            status=response.status,
            created=response.created,
            mqtt_topic=response.mqtt_topic,
        )

    def close(self) -> None:
        """Fecha o canal gRPC (chamado no shutdown da aplicação)."""
        self._channel.close()
