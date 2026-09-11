from unittest.mock import MagicMock

import paho.mqtt.client as mqtt

from agent.mqtt_consumer import DEFAULT_TOPIC, MqttConsumer


def _consumer_with_mock_client():
    consumer = MqttConsumer()
    consumer.client = MagicMock()
    return consumer


def test_on_connect_success_subscribes_to_topic():
    consumer = _consumer_with_mock_client()
    reason_code = mqtt.convert_connack_rc_to_reason_code(0)

    consumer.on_connect(consumer.client, None, None, reason_code, None)

    consumer.client.subscribe.assert_called_once_with(DEFAULT_TOPIC)


def test_on_connect_failure_does_not_subscribe():
    consumer = _consumer_with_mock_client()
    reason_code = mqtt.convert_connack_rc_to_reason_code(1)

    consumer.on_connect(consumer.client, None, None, reason_code, None)

    consumer.client.subscribe.assert_not_called()


def test_on_message_logs_topic_and_payload(caplog):
    consumer = _consumer_with_mock_client()
    message = MagicMock()
    message.topic = "application/1/device/abc123/event/up"
    message.payload = b'{"temperature": 25.5}'

    with caplog.at_level("INFO"):
        consumer.on_message(consumer.client, None, message)

    assert message.topic in caplog.text
    assert "temperature" in caplog.text


def test_config_defaults_when_env_unset(monkeypatch):
    for var in ("MQTT_BROKER_HOST", "MQTT_BROKER_PORT", "MQTT_TOPIC"):
        monkeypatch.delenv(var, raising=False)

    consumer = MqttConsumer()

    assert consumer.broker_host == "localhost"
    assert consumer.broker_port == 1883
    assert consumer.topic == DEFAULT_TOPIC


def test_config_reads_env_vars(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_BROKER_PORT", "8883")
    monkeypatch.setenv("MQTT_TOPIC", "custom/+/topic")

    consumer = MqttConsumer()

    assert consumer.broker_host == "broker.example.com"
    assert consumer.broker_port == 8883
    assert consumer.topic == "custom/+/topic"
