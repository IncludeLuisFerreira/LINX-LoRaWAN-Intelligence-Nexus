from routing.config import RoutingSettings


def test_settings_mqtt_defaults(monkeypatch):
    monkeypatch.delenv("MQTT_BROKER_HOST", raising=False)
    monkeypatch.delenv("MQTT_BROKER_PORT", raising=False)
    monkeypatch.delenv("MQTT_TOPIC", raising=False)
    monkeypatch.delenv("HTTP_TIMEOUT_SECONDS", raising=False)

    settings = RoutingSettings(_env_file=None)

    assert settings.mqtt_broker_host == "localhost"
    assert settings.mqtt_broker_port == 1883
    assert settings.mqtt_topic == "application/+/device/+/event/up"
    assert settings.http_timeout_seconds == 5.0


def test_settings_override_mqtt(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_BROKER_PORT", "8883")
    monkeypatch.setenv("MQTT_TOPIC", "custom/+/topic")
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "10")

    settings = RoutingSettings(_env_file=None)

    assert settings.mqtt_broker_host == "broker.example.com"
    assert settings.mqtt_broker_port == 8883
    assert settings.mqtt_topic == "custom/+/topic"
    assert settings.http_timeout_seconds == 10.0
