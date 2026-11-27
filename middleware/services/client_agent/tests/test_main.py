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


def test_health_rechecks_connectivity_after_ttl():
    with patch("agent.main.SaasGrpcClient") as client_cls:
        instance = client_cls.return_value
        instance.check_connectivity.return_value = True
        with TestClient(app) as client:
            assert client.get("/health").json()["saas_grpc"] is True

            instance.check_connectivity.return_value = False
            client.app.state.saas_checked_at = 0.0

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


def test_lifespan_forwards_mtls_paths(monkeypatch):
    monkeypatch.setenv("GRPC_CA_CERT_PATH", "/certs/ca.crt")
    monkeypatch.setenv("GRPC_CLIENT_CERT_PATH", "/certs/client.crt")
    monkeypatch.setenv("GRPC_CLIENT_KEY_PATH", "/certs/client.key")

    with patch("agent.main.SaasGrpcClient") as client_cls:
        client_cls.return_value.check_connectivity.return_value = False
        with TestClient(app):
            pass

    client_cls.assert_called_once()
    kwargs = client_cls.call_args.kwargs
    assert kwargs["ca_cert_path"] == "/certs/ca.crt"
    assert kwargs["client_cert_path"] == "/certs/client.crt"
    assert kwargs["client_key_path"] == "/certs/client.key"
