from unittest.mock import MagicMock, patch

import grpc
import pytest
from starlette.testclient import TestClient

from agent.grpc import saas_agent_pb2
from agent.grpc_client import (
    AgentBootstrapError,
    TenantRuntimeConfig,
    fetch_app_config,
)
from agent.main import app


def test_fetch_app_config_success():
    """Valida conversão correta dos dados retornados pelo stub gRPC."""
    mock_channel = MagicMock()
    mock_response = saas_agent_pb2.AppConfig(
        db_host="postgres-tenant", db_port=5432, mqtt_topic="app/tenant1/#"
    )

    with patch(
        "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"
    ) as mock_stub_cls:
        mock_stub = MagicMock()
        mock_stub.GetAppConfig.return_value = mock_response
        mock_stub_cls.return_value = mock_stub

        config = fetch_app_config(
            app_id="tenant1",
            server="localhost:50051",
            timeout=2.0,
            channel=mock_channel,
        )

        assert isinstance(config, TenantRuntimeConfig)
        assert config.db_host == "postgres-tenant"
        assert config.db_port == 5432
        assert config.mqtt_topic == "app/tenant1/#"
        mock_stub.GetAppConfig.assert_called_once()


def test_fetch_app_config_rpc_error_raises_bootstrap_error():
    """Valida se erros gRPC disparam AgentBootstrapError (fail-fast)."""
    mock_channel = MagicMock()

    with patch(
        "agent.grpc_client.saas_agent_pb2_grpc.AgentBridgeStub"
    ) as mock_stub_cls:
        mock_stub = MagicMock()
        mock_error = grpc.RpcError("Conexão recusada")
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = lambda: "Service Unavailable"
        mock_stub.GetAppConfig.side_effect = mock_error
        mock_stub_cls.return_value = mock_stub

        with pytest.raises(AgentBootstrapError) as exc_info:
            fetch_app_config(
                app_id="tenant1",
                server="localhost:50051",
                timeout=1.0,
                channel=mock_channel,
            )

        assert "StatusCode.UNAVAILABLE" in str(exc_info.value)


def test_lifespan_populates_app_state():
    """Valida se o lifespan do FastAPI armazena a configuração em app.state."""
    mock_config = TenantRuntimeConfig(
        db_host="timescaledb", db_port=5432, mqtt_topic="tenant/telemetry/#"
    )

    with patch("agent.main.fetch_app_config", return_value=mock_config):
        with TestClient(app) as client:
            assert client.app.state.app_config == mock_config
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
