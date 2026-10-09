from telemetry_consumer.config import ConsumerSettings


def test_queue_names_for_app_id():
    settings = ConsumerSettings(app_id="app-1")
    assert settings.queue_name == "linx.telemetry.app-1"
    assert settings.dead_letter_queue_name == "linx.telemetry.app-1.dlq"
    assert settings.binding_key == "application.app-1.#"


def test_defaults():
    settings = ConsumerSettings()
    assert settings.rabbit_exchange == "linx.telemetry"
    assert settings.rabbit_prefetch_count == 10
    assert settings.consumer_max_retries == 3


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_ID", "tenant-9")
    monkeypatch.setenv("CONSUMER_MAX_RETRIES", "7")
    settings = ConsumerSettings()
    assert settings.app_id == "tenant-9"
    assert settings.consumer_max_retries == 7
