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
    with (
        patch("agent.grpc_client.grpc.insecure_channel"),
        patch(
            "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub",
            return_value=stub,
        ),
    ):
        return SaasGrpcClient(
            server="localhost:50051", timeout=1.0, cache_ttl_seconds=60.0
        )


def test_channel_uses_configured_server():
    with (
        patch("agent.grpc_client.grpc.insecure_channel") as channel,
        patch("agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"),
    ):
        SaasGrpcClient("saas:50051", timeout=1.0)

    channel.assert_called_once_with("saas:50051")


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


def test_get_app_config_uses_cache():
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        db_host="h", db_port=1, mqtt_topic="t"
    )
    client = _client(stub)

    client.get_app_config("tenant1")
    client.get_app_config("tenant1")

    assert stub.GetAppConfig.call_count == 1


def test_get_app_config_refreshes_after_ttl():
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        db_host="h", db_port=1, mqtt_topic="t"
    )
    client = _client(stub)

    with patch("agent.grpc_client.time.monotonic", side_effect=[0.0, 61.0]):
        client.get_app_config("tenant1")
        client.get_app_config("tenant1")

    assert stub.GetAppConfig.call_count == 2


def test_check_connectivity_true_when_ready():
    future = MagicMock()
    future.result.return_value = None
    with (
        patch("agent.grpc_client.grpc.insecure_channel"),
        patch("agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"),
        patch(
            "agent.grpc_client.grpc.channel_ready_future", return_value=future
        ),
    ):
        client = SaasGrpcClient("localhost:50051", timeout=1.0)
        assert client.check_connectivity() is True


def test_check_connectivity_false_on_timeout():
    future = MagicMock()
    future.result.side_effect = grpc.FutureTimeoutError()
    with (
        patch("agent.grpc_client.grpc.insecure_channel"),
        patch("agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"),
        patch(
            "agent.grpc_client.grpc.channel_ready_future", return_value=future
        ),
    ):
        client = SaasGrpcClient("localhost:50051", timeout=1.0)
        assert client.check_connectivity() is False
