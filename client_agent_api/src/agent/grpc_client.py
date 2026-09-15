import logging
from dataclasses import dataclass

import grpc

from agent.grpc import saas_agent_pb2, saas_agent_pb2_grpc

logger = logging.getLogger(__name__)


class AgentBootstrapError(RuntimeError):
    """Exceção levantada quando o handshake gRPC inicial com o SaaS falha."""

    pass


@dataclass(frozen=True)
class TenantRuntimeConfig:
    db_host: str
    db_port: int
    mqtt_topic: str


def fetch_app_config(
    app_id: str,
    server: str = "saas:50051",
    timeout: float = 5.0,
    channel: grpc.Channel | None = None,
) -> TenantRuntimeConfig:
    """Solicita as configurações de runtime para o app_id via gRPC."""
    own_channel = False
    if channel is None:
        channel = grpc.insecure_channel(server)
        own_channel = True

    try:
        stub = saas_agent_pb2_grpc.AgentBridgeStub(channel)
        # Quebra de linha para respeitar limite de 79 caracteres
        request = saas_agent_pb2.AppId(  # type: ignore [attr-defined]
            app_id=app_id
        )

        logger.info(
            "Conectando ao SaaS gRPC em %s para app_id=%s (timeout=%.1fs)",
            server,
            app_id,
            timeout,
        )

        response = stub.GetAppConfig(request, timeout=timeout)

        config = TenantRuntimeConfig(
            db_host=response.db_host,
            db_port=response.db_port,
            mqtt_topic=response.mqtt_topic,
        )

        logger.info(
            "Configuração recebida com sucesso: db_host=%s, db_port=%d, "
            "mqtt_topic=%s",
            config.db_host,
            config.db_port,
            config.mqtt_topic,
        )
        return config

    except grpc.RpcError as rpc_err:
        status_code = (
            rpc_err.code() if hasattr(rpc_err, "code") else "UNKNOWN"
        )
        details = (
            rpc_err.details()
            if hasattr(rpc_err, "details")
            else str(rpc_err)
        )
        logger.critical(
            "Falha gRPC ao obter AppConfig: code=%s, details=%s",
            status_code,
            details,
        )
        raise AgentBootstrapError(
            f"Falha de conexão com SaaS Backend ({status_code}): {details}"
        ) from rpc_err
    except Exception as exc:
        logger.critical(
            "Erro inesperado durante o bootstrap gRPC: %s", exc
        )
        raise AgentBootstrapError(
            f"Erro inesperado no bootstrap: {exc}"
        ) from exc
    finally:
        if own_channel:
            channel.close()
