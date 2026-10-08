from agent_bridge.config import AgentBridgeSettings


def test_settings_grpc_defaults(monkeypatch):
    monkeypatch.delenv("GRPC_HOST", raising=False)
    monkeypatch.delenv("GRPC_PORT", raising=False)
    settings = AgentBridgeSettings(_env_file=None)
    assert settings.grpc_host == "0.0.0.0"
    assert settings.grpc_port == 50051


def test_settings_override_grpc(monkeypatch):
    monkeypatch.setenv("GRPC_HOST", "127.0.0.1")
    monkeypatch.setenv("GRPC_PORT", "6000")
    settings = AgentBridgeSettings(_env_file=None)
    assert settings.grpc_host == "127.0.0.1"
    assert settings.grpc_port == 6000
