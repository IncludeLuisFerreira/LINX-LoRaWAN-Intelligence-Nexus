import pytest
from pydantic import ValidationError

from agent_bridge.config import AgentBridgeSettings

_VALID_DB = "postgresql+psycopg://u:p@h:5432/db"


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


def test_startup_rejects_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        AgentBridgeSettings(_env_file=None)


def test_startup_rejects_default_database_credentials(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://linx:linx@localhost:5432/linx",
    )
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        AgentBridgeSettings(_env_file=None)


def test_startup_accepts_real_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _VALID_DB)
    settings = AgentBridgeSettings(_env_file=None)
    assert settings.database_url == _VALID_DB
