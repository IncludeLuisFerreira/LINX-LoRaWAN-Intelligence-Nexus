from pathlib import Path

import pytest

from tenant.config import TenantSettings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("APP_ID", raising=False)
    monkeypatch.delenv("SAAS_GRPC_HOST", raising=False)
    monkeypatch.delenv("GRPC_TIMEOUT_SECONDS", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = TenantSettings()

    assert settings.app_id == "app-abc123"
    assert settings.saas_grpc_host == "localhost:50051"
    assert settings.grpc_timeout_seconds == 5.0
