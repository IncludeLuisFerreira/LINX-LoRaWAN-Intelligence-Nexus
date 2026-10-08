import json
import queue
from unittest.mock import MagicMock

import paho.mqtt.client as mqtt

from routing.consumer import MqttConsumer
from routing.validation import ValidUplink


def _consumer():
    q = queue.Queue()
    consumer = MqttConsumer(
        broker_host="h",
        broker_port=1883,
        topic="application/+/device/+/event/up",
        qos=1,
        max_payload_bytes=65536,
        out_queue=q,
    )
    consumer.client = MagicMock()
    return consumer, q


def test_on_connect_subscribes_on_success():
    consumer, _ = _consumer()
    rc = mqtt.convert_connack_rc_to_reason_code(0)

    consumer.on_connect(consumer.client, None, None, rc, None)

    consumer.client.subscribe.assert_called_once_with(consumer.topic, qos=1)


def test_on_connect_failure_does_not_subscribe():
    consumer, _ = _consumer()
    rc = mqtt.convert_connack_rc_to_reason_code(1)

    consumer.on_connect(consumer.client, None, None, rc, None)

    consumer.client.subscribe.assert_not_called()


def test_on_message_enqueues_valid_uplink():
    consumer, q = _consumer()
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = json.dumps(
        {"object": {"t": 20}, "time": "2026-10-08T12:00:00Z"}
    ).encode()

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 1
    uplink = q.get_nowait()
    assert isinstance(uplink, ValidUplink)
    assert uplink.dev_eui == "devA"


def test_on_message_drops_invalid(caplog):
    consumer, q = _consumer()
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = b"not-json"

    with caplog.at_level("WARNING"):
        consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 0


def test_on_message_never_raises(monkeypatch):
    consumer, q = _consumer()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("routing.consumer.validate_message", boom)
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = b"{}"

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 0


def test_on_message_drops_when_queue_full(caplog):
    q = queue.Queue(maxsize=1)
    q.put("occupied")
    consumer = MqttConsumer(
        broker_host="h",
        broker_port=1883,
        topic="application/+/device/+/event/up",
        qos=1,
        max_payload_bytes=65536,
        out_queue=q,
    )
    consumer.client = MagicMock()
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = json.dumps({"object": {}, "time": "t"}).encode()

    with caplog.at_level("ERROR"):
        consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 1


def test_stop_disconnects_and_stops_loop():
    consumer, _ = _consumer()

    consumer.stop()

    consumer.client.disconnect.assert_called_once()
    consumer.client.loop_stop.assert_called_once()
