from unittest.mock import MagicMock, patch

import grpc
import pytest

from agent.grpc import saas_agent_pb2
from agent.grpc_client import (
    AgentBootstrapError,
    SaasGrpcClient,
    TenantRuntimeConfig,
)


def _client(stub: MagicMock) -> SaasGrpcClient:
    with patch("agent.grpc_client.grpc.insecure_channel"), patch(
        "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub",
        return_value=stub,
    ):
        return SaasGrpcClient(
            server="localhost:50051", timeout=1.0, cache_ttl_seconds=60.0
        )


def test_get_app_config_maps_response():
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        db_host="postgres-tenant", db_port=5432, mqtt_topic="app/tenant1/#"
    )
    client = _client(stub)

    config = client.get_app_config("tenant1")

    assert config == TenantRuntimeConfig(
        "postgres-tenant", 5432, "app/tenant1/#"
    )
    stub.GetAppConfig.assert_called_once()


def test_get_app_config_rpc_error_raises_bootstrap_error():
    stub = MagicMock()
    error = grpc.RpcError()
    error.code = lambda: grpc.StatusCode.NOT_FOUND
    error.details = lambda: "Aplicação não encontrada"
    stub.GetAppConfig.side_effect = error
    client = _client(stub)

    with pytest.raises(AgentBootstrapError) as exc:
        client.get_app_config("missing")

    assert "NOT_FOUND" in str(exc.value)
