import pytest
from pydantic import ValidationError

from identity_api.config import IdentitySettings

_VALID_DB = "postgresql+psycopg://u:p@h:5432/db"


def _valid_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _VALID_DB)
    monkeypatch.setenv("RABBITMQ_ADMIN_PASSWORD", "real-admin-pass")
    monkeypatch.setenv("RABBITMQ_TENANT_SECRET", "real-tenant-secret")


def test_startup_accepts_full_config(monkeypatch):
    _valid_env(monkeypatch)
    settings = IdentitySettings(_env_file=None)
    assert settings.database_url == _VALID_DB
    assert settings.rabbitmq_admin_password == "real-admin-pass"
    assert settings.rabbitmq_tenant_secret == "real-tenant-secret"


def test_startup_rejects_missing_rabbitmq_admin_password(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("RABBITMQ_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError, match="RABBITMQ_ADMIN_PASSWORD"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_placeholder_rabbitmq_admin_password(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("RABBITMQ_ADMIN_PASSWORD", "changeme")
    with pytest.raises(ValidationError, match="RABBITMQ_ADMIN_PASSWORD"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_missing_tenant_secret(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("RABBITMQ_TENANT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="RABBITMQ_TENANT_SECRET"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_missing_database_url(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_default_database_credentials(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://linx:linx@localhost:5432/linx",
    )
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        IdentitySettings(_env_file=None)
