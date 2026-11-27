import pytest

from linx_shared.core.config import Settings, require_secret


def test_settings_database_url_has_no_insecure_default(monkeypatch):
    # #210: o default inseguro (linx:linx) foi removido. A base não impõe
    # validador — routing herda de Settings e não usa banco; quem constrói a
    # engine (identity_api, agent_bridge) valida no startup.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url == ""


def test_settings_override_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/db")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+psycopg://u:p@db:5432/db"


def test_settings_db_connect_timeout_default(monkeypatch):
    monkeypatch.delenv("DB_CONNECT_TIMEOUT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.db_connect_timeout == 2


def test_settings_override_db_connect_timeout(monkeypatch):
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "5")
    settings = Settings(_env_file=None)
    assert settings.db_connect_timeout == 5


def test_require_secret_rejects_value_shorter_than_minimum():
    with pytest.raises(ValueError, match="at least 32"):
        require_secret("PROVISIONER_SERVICE_TOKEN", "short", min_length=32)


def test_require_secret_accepts_value_at_minimum_length():
    value = "x" * 32

    assert (
        require_secret("PROVISIONER_SERVICE_TOKEN", value, min_length=32)
        == value
    )
