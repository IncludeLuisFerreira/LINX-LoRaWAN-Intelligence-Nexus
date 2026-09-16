import logging
import time
from dataclasses import dataclass

import grpc

from agent.grpc import saas_agent_pb2, saas_agent_pb2_grpc

logger = logging.getLogger(__name__)


class AgentBootstrapError(RuntimeError):
    """Falha de comunicação com o SaaS Backend."""


@dataclass(frozen=True)
class TenantRuntimeConfig:
    db_host: str
    db_port: int
    mqtt_topic: str


class SaasGrpcClient:
    def __init__(
        self,
        server: str,
        timeout: float = 5.0,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self._server = server
        self._timeout = timeout
        self._cache_ttl = cache_ttl_seconds
        self._channel = grpc.insecure_channel(self._server)
        self._stub = saas_agent_pb2_grpc.AgentBridgeStub(self._channel)
        self._cache: dict[str, tuple[TenantRuntimeConfig, float]] = {}

    def get_app_config(self, app_id: str) -> TenantRuntimeConfig:
        now = time.monotonic()
        cached = self._cache.get(app_id)
        if cached is not None and cached[1] > now:
            return cached[0]

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
            logger.critical(
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
            logger.critical(
                "SaaS Backend inacessível em %s: %s", self._server, err
            )
            return False

    def close(self) -> None:
        self._channel.close()
