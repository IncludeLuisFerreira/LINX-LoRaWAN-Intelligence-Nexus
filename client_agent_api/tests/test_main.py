from unittest.mock import patch

from starlette.testclient import TestClient

from agent.main import app


def test_health_reports_saas_connectivity():
    with patch("agent.main.SaasGrpcClient") as client_cls:
        client_cls.return_value.check_connectivity.return_value = True
        with TestClient(app) as client:
            assert client.get("/health").json() == {
                "status": "ok",
                "saas_grpc": True,
            }


def test_health_degraded_when_saas_unreachable():
    with patch("agent.main.SaasGrpcClient") as client_cls:
        client_cls.return_value.check_connectivity.return_value = False
        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "saas_grpc": False}


def test_lifespan_registers_and_closes_client():
    with patch("agent.main.SaasGrpcClient") as client_cls:
        instance = client_cls.return_value
        instance.check_connectivity.return_value = False
        with TestClient(app) as client:
            assert client.app.state.saas_client is instance
            assert client.app.state.saas_connected is False
        instance.close.assert_called_once()
