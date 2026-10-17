import logging
import os
import time
from dataclasses import dataclass

import grpc

from agent.grpc import linx_agent_pb2, linx_agent_pb2_grpc

logger = logging.getLogger(__name__)

TOKEN_ENV = "GRPC_SERVICE_TOKEN"
CA_CERT_ENV = "GRPC_CA_CERT_PATH"


class AgentBootstrapError(RuntimeError):
    """Falha de comunicação com o Linx Core."""


@dataclass(frozen=True)
class TenantRuntimeConfig:
    db_host: str
    db_port: int
    mqtt_topic: str


def _build_channel(server: str, ca_cert_path: str | None) -> grpc.Channel:
    """Canal seguro quando há CA configurada; inseguro apenas em dev."""
    if ca_cert_path:
        with open(ca_cert_path, "rb") as handle:
            root_ca = handle.read()
        credentials = grpc.ssl_channel_credentials(root_certificates=root_ca)
        return grpc.secure_channel(server, credentials)
    logger.warning(
        "Conectando ao Linx Core em %s sem TLS (canal inseguro). "
        "Configure GRPC_CA_CERT_PATH em produção.",
        server,
    )
    return grpc.insecure_channel(server)


class SaasGrpcClient:
    def __init__(
        self,
        server: str,
        timeout: float = 5.0,
        cache_ttl_seconds: float = 60.0,
        service_token: str | None = None,
        ca_cert_path: str | None = None,
    ) -> None:
        self._server = server
        self._timeout = timeout
        self._cache_ttl = cache_ttl_seconds
        self._service_token = (
            service_token
            if service_token is not None
            else os.environ.get(TOKEN_ENV, "")
        )
        resolved_ca = (
            ca_cert_path
            if ca_cert_path is not None
            else os.environ.get(CA_CERT_ENV, "")
        )
        self._metadata: list[tuple[str, str]] = []
        if self._service_token:
            self._metadata.append(
                ("authorization", f"Bearer {self._service_token}")
            )
        else:
            logger.warning(
                "GRPC_SERVICE_TOKEN ausente; chamadas ao Linx Core serão "
                "recusadas com UNAUTHENTICATED."
            )
        self._channel = _build_channel(self._server, resolved_ca or None)
        self._stub = linx_agent_pb2_grpc.AgentBridgeStub(self._channel)
        self._cache: dict[str, tuple[TenantRuntimeConfig, float]] = {}

    def get_app_config(self, app_id: str) -> TenantRuntimeConfig:
        now = time.monotonic()
        cached = self._cache.get(app_id)
        if cached is not None and cached[1] > now:
            return cached[0]

        request = linx_agent_pb2.AppId(  # type: ignore[attr-defined]
            app_id=app_id
        )
        try:
            response = self._stub.GetAppConfig(
                request,
                timeout=self._timeout,
                metadata=self._metadata,
            )
        except grpc.RpcError as rpc_err:
            code = rpc_err.code() if hasattr(rpc_err, "code") else "UNKNOWN"
            details = (
                rpc_err.details()
                if hasattr(rpc_err, "details")
                else str(rpc_err)
            )
            logger.error(
                "Falha gRPC GetAppConfig app_id=%s code=%s details=%s",
                app_id,
                code,
                details,
            )
            raise AgentBootstrapError(
                f"Falha ao obter AppConfig ({code}): {details}"
            ) from rpc_err

        config = TenantRuntimeConfig(
            db_host=response.db_host,
            db_port=response.db_port,
            mqtt_topic=response.mqtt_topic,
        )
        self._cache[app_id] = (config, now + self._cache_ttl)
        return config

    def check_connectivity(self) -> bool:
        try:
            grpc.channel_ready_future(self._channel).result(
                timeout=self._timeout
            )
            return True
        except Exception as err:
            logger.warning(
                "Linx Core inacessível em %s: %s", self._server, err
            )
            return False

    def close(self) -> None:
        self._channel.close()
