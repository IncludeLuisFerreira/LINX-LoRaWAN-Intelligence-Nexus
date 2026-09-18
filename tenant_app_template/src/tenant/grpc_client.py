import logging
from typing import Any

import grpc

from tenant.grpc import saas_agent_pb2, saas_agent_pb2_grpc

logger = logging.getLogger(__name__)


class TenantBootstrapError(RuntimeError):
    """Falha de comunicação com o SaaS Backend."""


class SaasConfigClient:
    def __init__(self, server: str, timeout: float = 5.0) -> None:
        self._server = server
        self._timeout = timeout
        self._channel = grpc.insecure_channel(self._server)
        self._stub = saas_agent_pb2_grpc.AgentBridgeStub(self._channel)

    def get_app_config(self, app_id: str) -> Any:
        request = saas_agent_pb2.AppId(  # type: ignore[attr-defined]
            app_id=app_id
        )
        try:
            response = self._stub.GetAppConfig(request, timeout=self._timeout)
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
            raise TenantBootstrapError(
                f"Falha ao obter AppConfig ({code}): {details}"
            ) from rpc_err

        logger.info(
            "AppConfig received app_id=%s db_host=%s db_port=%s mqtt_topic=%s",
            app_id,
            response.db_host,
            response.db_port,
            response.mqtt_topic,
        )
        return response

    def close(self) -> None:
        self._channel.close()
