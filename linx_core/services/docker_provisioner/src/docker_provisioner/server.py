import logging
import secrets
from collections.abc import Iterable
from concurrent import futures
from uuid import UUID

import docker
import grpc
import requests
from linx_shared.grpc import (
    linx_docker_provisioner_pb2,
    linx_docker_provisioner_pb2_grpc,
)

from docker_provisioner.config import settings
from docker_provisioner.docker_service import (
    ProvisioningError,
    provision_application,
)

logger = logging.getLogger(__name__)

AUTH_METADATA_KEY = "authorization"
BEARER_PREFIX = "Bearer "
MIN_SERVICE_TOKEN_LENGTH = 32
PLACEHOLDER_SERVICE_TOKENS = frozenset(
    {"changeme", "change-me", "change-me-in-production"}
)
_UNAUTHENTICATED_DETAILS = "Not authorized"


def _extract_bearer_token(
    invocation_metadata: Iterable[tuple[str, str]] | None,
) -> str | None:
    """Extrai o token do metadado `authorization: Bearer <token>`."""
    for key, value in invocation_metadata or ():
        if key.lower() == AUTH_METADATA_KEY and value.startswith(
            BEARER_PREFIX
        ):
            prefix_len = len(BEARER_PREFIX)
            return value[prefix_len:].strip()
    return None


def ensure_service_token() -> None:
    """Falha o startup se o token estiver ausente ou fraco.

    O mesmo token autentica a chamada do identity_api e é injetado no
    container do tenant; por isso ele precisa ser um segredo real.
    """
    token = (settings.service_token or "").strip()
    if not token:
        raise RuntimeError("SERVICE_TOKEN is not configured.")
    if token in PLACEHOLDER_SERVICE_TOKENS:
        raise RuntimeError(
            "SERVICE_TOKEN uses a known placeholder value; "
            "set a unique random secret."
        )
    if len(token) < MIN_SERVICE_TOKEN_LENGTH:
        raise RuntimeError(
            f"SERVICE_TOKEN must be at least "
            f"{MIN_SERVICE_TOKEN_LENGTH} characters long."
        )


def authorize(context) -> None:
    """Valida o token de serviço nos metadados da chamada gRPC.

    Falha fechada e em tempo constante: qualquer chamada sem o metadado
    correto é recusada como UNAUTHENTICATED, sem vazar o segredo esperado.
    """
    expected = settings.service_token
    if not expected:
        logger.error("SERVICE_TOKEN não configurado; recusando chamada gRPC.")
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED, _UNAUTHENTICATED_DETAILS
        )

    provided = _extract_bearer_token(context.invocation_metadata()) or ""
    if not secrets.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED, _UNAUTHENTICATED_DETAILS
        )


class DockerProvisionerServicer(
    linx_docker_provisioner_pb2_grpc.DockerProvisionerServicer
):
    """Implementação gRPC do provisionamento Docker por aplicação."""

    def __init__(self, client_factory=None) -> None:
        # O client é criado sob demanda para que o servidor gRPC suba mesmo
        # quando o Docker ainda não estiver disponível; cada chamada falha
        # com UNAVAILABLE nesse caso.
        self._client_factory = client_factory or docker.from_env

    def ProvisionApplication(self, request, context):
        authorize(context)

        try:
            app_id = str(UUID(request.app_id))
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"app_id inválido: {request.app_id}",
            )

        try:
            client = self._client_factory()
            try:
                result = provision_application(
                    client,
                    app_id,
                    image=settings.provision_image,
                    port_min=settings.provision_port_min,
                    port_max=settings.provision_port_max,
                    bind_host=settings.provision_bind_host,
                    network_prefix=settings.provision_network_prefix,
                    container_port=settings.provision_container_port,
                    service_token=settings.service_token,
                )
            finally:
                # Cada requisição cria um DockerClient; fecha a sessão HTTP
                # subjacente para não deixar conexões acumuladas.
                client.close()
        except ProvisioningError as exc:
            context.abort(exc.status, exc.message)
        except (
            docker.errors.DockerException,
            requests.exceptions.RequestException,
        ):
            logger.exception("Falha ao obter client Docker")
            context.abort(
                grpc.StatusCode.UNAVAILABLE,
                "Docker daemon is unavailable",
            )

        return linx_docker_provisioner_pb2.ProvisionApplicationResponse(
            container_id=result.container_id,
            port=result.port,
            network=result.network,
            image=result.image,
            status=result.status,
            created=result.created,
            mqtt_topic=result.mqtt_topic,
        )


def _build_bind_address(host: str, port: int) -> str:
    if ":" in host:
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def create_server(
    servicer: DockerProvisionerServicer | None = None,
) -> grpc.Server:
    """Cria o servidor gRPC e faz bind no endereço configurado."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    if servicer is None:
        servicer = DockerProvisionerServicer()
    linx_docker_provisioner_pb2_grpc.add_DockerProvisionerServicer_to_server(
        servicer, server
    )

    bind_address = _build_bind_address(settings.grpc_host, settings.grpc_port)
    port = server.add_insecure_port(bind_address)
    if port == 0:
        raise RuntimeError(
            f"Não foi possível fazer bind do servidor gRPC em "
            f"{bind_address}"
        )

    logger.warning(
        "Servindo gRPC em modo inseguro em %s. A autorização por "
        "metadado (SERVICE_TOKEN) é a única barreira; mantenha a porta "
        "restrita à rede interna até haver TLS.",
        bind_address,
    )
    return server


def serve() -> None:
    """Valida o token, inicia o servidor e aguarda terminação."""
    ensure_service_token()
    server = create_server()
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
