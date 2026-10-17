from agent_bridge.config import AgentBridgeSettings


def test_settings_grpc_defaults(monkeypatch):
    monkeypatch.delenv("GRPC_HOST", raising=False)
    monkeypatch.delenv("GRPC_PORT", raising=False)
    monkeypatch.delenv("AGENT_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("GRPC_CERT_CHAIN_PATH", raising=False)
    monkeypatch.delenv("GRPC_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.delenv("GRPC_CA_CERT_PATH", raising=False)
    settings = AgentBridgeSettings(_env_file=None)
    assert settings.grpc_host == "127.0.0.1"
    assert settings.grpc_port == 50051
    assert settings.agent_service_token == ""
    assert settings.grpc_cert_chain_path == ""
    assert settings.grpc_private_key_path == ""
    assert settings.grpc_ca_cert_path == ""


def test_settings_override_grpc(monkeypatch):
    monkeypatch.setenv("GRPC_HOST", "127.0.0.1")
    monkeypatch.setenv("GRPC_PORT", "6000")
    settings = AgentBridgeSettings(_env_file=None)
    assert settings.grpc_host == "127.0.0.1"
    assert settings.grpc_port == 6000


def test_settings_reads_agent_token_and_tls(monkeypatch):
    monkeypatch.setenv("AGENT_SERVICE_TOKEN", "s" * 40)
    monkeypatch.setenv("GRPC_CERT_CHAIN_PATH", "/certs/server.crt")
    monkeypatch.setenv("GRPC_PRIVATE_KEY_PATH", "/certs/server.key")
    monkeypatch.setenv("GRPC_CA_CERT_PATH", "/certs/ca.crt")
    settings = AgentBridgeSettings(_env_file=None)
    assert settings.agent_service_token == "s" * 40
    assert settings.grpc_cert_chain_path == "/certs/server.crt"
    assert settings.grpc_private_key_path == "/certs/server.key"
    assert settings.grpc_ca_cert_path == "/certs/ca.crt"
