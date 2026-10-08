from routing.config import RoutingSettings


def test_settings_defaults(monkeypatch):
    for var in (
        "MQTT_BROKER_HOST",
        "MQTT_BROKER_PORT",
        "MQTT_TOPIC",
        "MQTT_QOS",
        "RABBIT_URL",
        "RABBIT_EXCHANGE",
        "MAX_PAYLOAD_BYTES",
        "RABBIT_CONNECT_MAX_ATTEMPTS",
        "RABBIT_CONNECT_BACKOFF_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = RoutingSettings(_env_file=None)

    assert settings.mqtt_broker_host == "localhost"
    assert settings.mqtt_broker_port == 1883
    assert settings.mqtt_topic == "application/+/device/+/event/up"
    assert settings.mqtt_qos == 1
    assert settings.rabbit_url == "amqp://guest:guest@localhost:5672/%2f"
    assert settings.rabbit_exchange == "linx.telemetry"
    assert settings.max_payload_bytes == 65536
    assert settings.rabbit_connect_max_attempts == 5
    assert settings.rabbit_connect_backoff_seconds == 1.0


def test_settings_override(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_BROKER_PORT", "8883")
    monkeypatch.setenv("MQTT_QOS", "0")
    monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/%2f")
    monkeypatch.setenv("RABBIT_EXCHANGE", "custom.telemetry")
    monkeypatch.setenv("MAX_PAYLOAD_BYTES", "1024")

    settings = RoutingSettings(_env_file=None)

    assert settings.mqtt_broker_host == "broker.example.com"
    assert settings.mqtt_broker_port == 8883
    assert settings.mqtt_qos == 0
    assert settings.rabbit_url == "amqp://guest:guest@rabbitmq:5672/%2f"
    assert settings.rabbit_exchange == "custom.telemetry"
    assert settings.max_payload_bytes == 1024
