from unittest.mock import MagicMock, patch

import grpc
import pytest

from tenant.grpc import saas_agent_pb2
from tenant.grpc_client import SaasConfigClient, TenantBootstrapError


def _client(stub: MagicMock) -> SaasConfigClient:
    with (
        patch("tenant.grpc_client.grpc.insecure_channel"),
        patch(
            "tenant.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub",
            return_value=stub,
        ),
    ):
        return SaasConfigClient(server="localhost:50051", timeout=1.0)


def test_channel_uses_configured_server():
    with (
        patch("tenant.grpc_client.grpc.insecure_channel") as channel,
        patch("tenant.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"),
    ):
        SaasConfigClient("localhost:50051", timeout=1.0)

    channel.assert_called_once_with("localhost:50051")


def test_close_closes_channel():
    with (
        patch("tenant.grpc_client.grpc.insecure_channel") as channel,
        patch("tenant.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"),
    ):
        client = SaasConfigClient("localhost:50051", timeout=1.0)
        client.close()

    channel.return_value.close.assert_called_once_with()


def test_get_app_config_maps_and_logs(caplog):
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        app_id="app-abc123",
        db_host="postgres-tenant",
        db_port=5432,
        db_name="tenantdb",
        db_user="secret-user",
        db_password="secret-pass",
        mqtt_topic="app/tenant1/#",
    )
    client = _client(stub)

    with caplog.at_level("INFO"):
        config = client.get_app_config("app-abc123")

    assert config.db_host == "postgres-tenant"
    assert config.db_port == 5432
    assert config.mqtt_topic == "app/tenant1/#"
    stub.GetAppConfig.assert_called_once()
    assert "AppConfig received" in caplog.text


def test_get_app_config_does_not_log_secrets(caplog):
    stub = MagicMock()
    stub.GetAppConfig.return_value = saas_agent_pb2.AppConfig(
        app_id="app-abc123",
        db_host="postgres-tenant",
        db_port=5432,
        db_name="tenantdb",
        db_user="secret-user",
        db_password="secret-pass",
        mqtt_topic="app/tenant1/#",
    )
    client = _client(stub)

    with caplog.at_level("INFO"):
        client.get_app_config("app-abc123")

    assert "secret-user" not in caplog.text
    assert "secret-pass" not in caplog.text


def test_get_app_config_rpc_error_raises_bootstrap_error():
    stub = MagicMock()
    error = grpc.RpcError()
    error.code = lambda: grpc.StatusCode.NOT_FOUND
    error.details = lambda: "Aplicação não encontrada"
    stub.GetAppConfig.side_effect = error
    client = _client(stub)

    with pytest.raises(TenantBootstrapError) as exc:
        client.get_app_config("missing")

    assert "NOT_FOUND" in str(exc.value)
