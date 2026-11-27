import logging
import os
import time
from dataclasses import dataclass

import grpc
from linx_shared.grpc import linx_agent_pb2, linx_agent_pb2_grpc

logger = logging.getLogger(__name__)

TOKEN_ENV = "GRPC_SERVICE_TOKEN"
CA_CERT_ENV = "GRPC_CA_CERT_PATH"
CLIENT_CERT_ENV = "GRPC_CLIENT_CERT_PATH"
CLIENT_KEY_ENV = "GRPC_CLIENT_KEY_PATH"


class AgentBootstrapError(RuntimeError):
    """Falha de comunicação com o Linx Core."""


@dataclass(frozen=True)
class TenantRuntimeConfig:
    db_host: str
    db_port: int
    mqtt_topic: str


def _read_tls_file(path: str, label: str) -> bytes:
    """Lê certificado/chave em bytes, falhando com erro explícito."""
    try:
        with open(path, "rb") as handle:
            content = handle.read()
    except OSError as err:
        raise RuntimeError(
            f"Não foi possível ler {label} em {path}: {err}"
        ) from err
    if not content:
        raise RuntimeError(f"Arquivo de {label} vazio: {path}")
    return content


def _build_channel(
    server: str,
    ca_cert_path: str | None,
    client_cert_path: str | None = None,
    client_key_path: str | None = None,
) -> grpc.Channel:
    """Canal mTLS com CA e par cliente; inseguro apenas em dev.

    A presença de apenas parte das credenciais é erro de configuração: o
    servidor exige certificado do cliente, então um canal sem ele falharia
    de qualquer forma. Falhar no startup deixa o problema explícito.
    """
    if not any((ca_cert_path, client_cert_path, client_key_path)):
        logger.warning(
            "Conectando ao Linx Core em %s sem mTLS (canal inseguro). "
            "Configure GRPC_CA_CERT_PATH, GRPC_CLIENT_CERT_PATH e "
            "GRPC_CLIENT_KEY_PATH em produção.",
            server,
        )
        return grpc.insecure_channel(server)
    if not ca_cert_path:
        raise RuntimeError(
            "GRPC_CA_CERT_PATH é obrigatório quando o certificado do "
            "cliente gRPC é configurado."
        )
    if not client_cert_path or not client_key_path:
        raise RuntimeError(
            "mTLS do gRPC exige GRPC_CLIENT_CERT_PATH e "
            "GRPC_CLIENT_KEY_PATH juntos (ou nenhum, apenas em dev)."
        )

    credentials = grpc.ssl_channel_credentials(
        root_certificates=_read_tls_file(ca_cert_path, "CA do gRPC"),
        certificate_chain=_read_tls_file(
            client_cert_path, "certificado do cliente gRPC"
        ),
        private_key=_read_tls_file(client_key_path, "chave do cliente gRPC"),
    )
    logger.info(
        "Canal gRPC mTLS configurado para %s (cert=%s)",
        server,
        client_cert_path,
    )
    return grpc.secure_channel(server, credentials)


class SaasGrpcClient:
    def __init__(
        self,
        server: str,
        timeout: float = 5.0,
        cache_ttl_seconds: float = 60.0,
        service_token: str | None = None,
        ca_cert_path: str | None = None,
        client_cert_path: str | None = None,
        client_key_path: str | None = None,
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
        resolved_client_cert = (
            client_cert_path
            if client_cert_path is not None
            else os.environ.get(CLIENT_CERT_ENV, "")
        )
        resolved_client_key = (
            client_key_path
            if client_key_path is not None
            else os.environ.get(CLIENT_KEY_ENV, "")
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
        self._channel = _build_channel(
            self._server,
            resolved_ca or None,
            resolved_client_cert or None,
            resolved_client_key or None,
        )
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
