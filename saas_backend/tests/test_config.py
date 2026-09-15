from linx.core.config import Settings


def test_settings_default_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url == (
        "postgresql+psycopg://linx:linx@localhost:5432/linx"
    )


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


def test_settings_grpc_defaults(monkeypatch):
    monkeypatch.delenv("GRPC_HOST", raising=False)
    monkeypatch.delenv("GRPC_PORT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.grpc_host == "0.0.0.0"
    assert settings.grpc_port == 50051


def test_settings_override_grpc(monkeypatch):
    monkeypatch.setenv("GRPC_HOST", "127.0.0.1")
    monkeypatch.setenv("GRPC_PORT", "6000")
    settings = Settings(_env_file=None)
    assert settings.grpc_host == "127.0.0.1"
    assert settings.grpc_port == 6000
