import pytest
from pydantic import ValidationError

from telemetry_consumer.config import ConsumerSettings

_VALID_RABBIT = "amqp://tenant:secret@localhost:5672/%2f"
_VALID_DB_PASSWORD = "tenant-real-pass"


def _valid_env(monkeypatch):
    monkeypatch.setenv("RABBIT_URL", _VALID_RABBIT)
    monkeypatch.setenv("DB_PASSWORD", _VALID_DB_PASSWORD)


def test_queue_names_for_app_id():
    settings = ConsumerSettings(app_id="app-1")
    assert settings.queue_name == "linx.telemetry.app-1"
    assert settings.dead_letter_queue_name == "linx.telemetry.app-1.dlq"
    assert settings.binding_key == "application.app-1.#"


def test_exchange_name_is_derived_from_app_id():
    settings = ConsumerSettings(app_id="app-1")
    assert settings.rabbit_exchange == "linx.telemetry.app-1"


def test_defaults():
    settings = ConsumerSettings()
    assert settings.rabbit_prefetch_count == 10
    assert settings.consumer_max_retries == 3


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_ID", "tenant-9")
    monkeypatch.setenv("CONSUMER_MAX_RETRIES", "7")
    settings = ConsumerSettings()
    assert settings.app_id == "tenant-9"
    assert settings.consumer_max_retries == 7
    assert settings.rabbit_exchange == "linx.telemetry.tenant-9"


def test_startup_rejects_missing_rabbit_url(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("RABBIT_URL", raising=False)
    with pytest.raises(ValidationError, match="RABBIT_URL"):
        ConsumerSettings(_env_file=None)


def test_startup_rejects_guest_rabbit_url(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/%2f")
    with pytest.raises(ValidationError, match="RABBIT_URL"):
        ConsumerSettings(_env_file=None)


def test_startup_rejects_missing_db_password(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(ValidationError, match="DB_PASSWORD"):
        ConsumerSettings(_env_file=None)


def test_startup_rejects_placeholder_db_password(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("DB_PASSWORD", "changeme")
    with pytest.raises(ValidationError, match="DB_PASSWORD"):
        ConsumerSettings(_env_file=None)


def test_startup_rejects_missing_service_token(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    with pytest.raises(ValidationError, match="SERVICE_TOKEN"):
        ConsumerSettings(_env_file=None)


def test_startup_rejects_placeholder_service_token(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("SERVICE_TOKEN", "changeme")
    with pytest.raises(ValidationError, match="SERVICE_TOKEN"):
        ConsumerSettings(_env_file=None)


def test_startup_accepts_full_config(monkeypatch):
    _valid_env(monkeypatch)
    settings = ConsumerSettings(_env_file=None)
    assert settings.rabbit_url == _VALID_RABBIT
    assert settings.db_password == _VALID_DB_PASSWORD
