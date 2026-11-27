from unittest.mock import MagicMock, patch

import grpc
import pytest
from linx_shared.grpc import linx_agent_pb2

from agent.grpc_client import (
    AgentBootstrapError,
    SaasGrpcClient,
    TenantRuntimeConfig,
)


def _client(stub: MagicMock) -> SaasGrpcClient:
    with (
        patch("agent.grpc_client.grpc.insecure_channel"),
        patch(
            "agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub",
            return_value=stub,
        ),
    ):
        return SaasGrpcClient(
            server="localhost:50051", timeout=1.0, cache_ttl_seconds=60.0
        )


def test_channel_uses_configured_server():
    with (
        patch("agent.grpc_client.grpc.insecure_channel") as channel,
        patch("agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub"),
    ):
        SaasGrpcClient("saas:50051", timeout=1.0)

    channel.assert_called_once_with("saas:50051")


def test_close_closes_channel():
    with (
        patch("agent.grpc_client.grpc.insecure_channel") as channel,
        patch("agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub"),
    ):
        client = SaasGrpcClient("saas:50051", timeout=1.0)
        client.close()

    channel.return_value.close.assert_called_once_with()


def test_get_app_config_maps_response():
    stub = MagicMock()
    stub.GetAppConfig.return_value = linx_agent_pb2.AppConfig(
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
    stub.GetAppConfig.return_value = linx_agent_pb2.AppConfig(
        db_host="h", db_port=1, mqtt_topic="t"
    )
    client = _client(stub)

    client.get_app_config("tenant1")
    client.get_app_config("tenant1")

    assert stub.GetAppConfig.call_count == 1


def test_get_app_config_refreshes_after_ttl():
    stub = MagicMock()
    stub.GetAppConfig.return_value = linx_agent_pb2.AppConfig(
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
        patch("agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub"),
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
        patch("agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub"),
        patch(
            "agent.grpc_client.grpc.channel_ready_future", return_value=future
        ),
    ):
        client = SaasGrpcClient("localhost:50051", timeout=1.0)
        assert client.check_connectivity() is False


def _fake_mtls_files(tmp_path):
    ca = tmp_path / "ca.crt"
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"
    ca.write_bytes(b"ca")
    cert.write_bytes(b"cert")
    key.write_bytes(b"key")
    return ca, cert, key


def test_channel_uses_mtls_credentials(tmp_path):
    ca, cert, key = _fake_mtls_files(tmp_path)

    with (
        patch(
            "agent.grpc_client.grpc.ssl_channel_credentials",
            return_value="creds",
        ) as credentials,
        patch("agent.grpc_client.grpc.secure_channel") as secure_channel,
        patch("agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub"),
    ):
        SaasGrpcClient(
            "saas:50051",
            ca_cert_path=str(ca),
            client_cert_path=str(cert),
            client_key_path=str(key),
        )

    credentials.assert_called_once_with(
        root_certificates=b"ca",
        certificate_chain=b"cert",
        private_key=b"key",
    )
    secure_channel.assert_called_once_with("saas:50051", "creds")


def test_channel_reads_mtls_paths_from_env(monkeypatch, tmp_path):
    ca, cert, key = _fake_mtls_files(tmp_path)
    monkeypatch.setenv("GRPC_CA_CERT_PATH", str(ca))
    monkeypatch.setenv("GRPC_CLIENT_CERT_PATH", str(cert))
    monkeypatch.setenv("GRPC_CLIENT_KEY_PATH", str(key))

    with (
        patch(
            "agent.grpc_client.grpc.ssl_channel_credentials",
            return_value="creds",
        ) as credentials,
        patch("agent.grpc_client.grpc.secure_channel"),
        patch("agent.grpc_client.linx_agent_pb2_grpc.AgentBridgeStub"),
    ):
        SaasGrpcClient("saas:50051")

    credentials.assert_called_once_with(
        root_certificates=b"ca",
        certificate_chain=b"cert",
        private_key=b"key",
    )


def test_channel_rejects_partial_mtls_config(tmp_path):
    ca, cert, key = _fake_mtls_files(tmp_path)

    with pytest.raises(RuntimeError, match="GRPC_CA_CERT_PATH"):
        SaasGrpcClient(
            "saas:50051",
            client_cert_path=str(cert),
            client_key_path=str(key),
        )

    with pytest.raises(RuntimeError, match="GRPC_CLIENT_CERT_PATH"):
        SaasGrpcClient("saas:50051", ca_cert_path=str(ca))


def test_channel_rejects_unreadable_ca(tmp_path):
    _, cert, key = _fake_mtls_files(tmp_path)

    with pytest.raises(RuntimeError, match="CA do gRPC"):
        SaasGrpcClient(
            "saas:50051",
            ca_cert_path=str(tmp_path / "missing.crt"),
            client_cert_path=str(cert),
            client_key_path=str(key),
        )
