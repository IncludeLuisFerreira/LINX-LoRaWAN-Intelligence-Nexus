from pathlib import Path

import pytest

from agent.config import AgentSettings


def test_settings_have_no_app_id():
    settings = AgentSettings()
    assert not hasattr(settings, "app_id")


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("SAAS_GRPC_HOST", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = AgentSettings()

    assert settings.saas_grpc_host == "agent_bridge:50051"
    assert settings.grpc_timeout_seconds == 5.0
    assert settings.config_cache_ttl_seconds == 60.0
