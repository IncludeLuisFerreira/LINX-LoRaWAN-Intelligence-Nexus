import json
import queue
import threading
from unittest.mock import MagicMock

import paho.mqtt.client as mqtt

from routing import consumer as consumer_module
from routing.consumer import MqttConsumer, PendingUplink
from routing.validation import ValidUplink


def _consumer(**kwargs):
    q = kwargs.pop("out_queue", None) or queue.Queue()
    consumer = MqttConsumer(
        broker_host="h",
        broker_port=1883,
        topic="application/+/device/+/event/up",
        qos=1,
        max_payload_bytes=65536,
        out_queue=q,
        **kwargs,
    )
    consumer.client = MagicMock()
    return consumer, q


def _message(
    payload=None, mid=7, qos=1, topic="application/app1/device/devA/event/up"
):
    message = MagicMock()
    message.topic = topic
    message.mid = mid
    message.qos = qos
    message.payload = payload
    return message


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


def test_on_message_enqueues_pending_uplink():
    consumer, q = _consumer()
    message = _message(
        json.dumps(
            {"object": {"t": 20}, "time": "2026-10-08T12:00:00Z"}
        ).encode(),
        mid=42,
        qos=1,
    )

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 1
    pending = q.get_nowait()
    assert isinstance(pending, PendingUplink)
    assert isinstance(pending.uplink, ValidUplink)
    assert pending.uplink.dev_eui == "devA"
    assert pending.mid == 42
    assert pending.qos == 1
    consumer.client.ack.assert_not_called()


def test_on_message_drops_invalid():
    consumer, q = _consumer()
    message = _message(b"not-json", mid=3, qos=1)

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 0
    consumer.client.ack.assert_called_once_with(3, 1)


def test_on_message_never_raises(monkeypatch):
    consumer, q = _consumer()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("routing.consumer.validate_message", boom)
    message = _message(b"{}", mid=4, qos=1)

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 0
    consumer.client.ack.assert_called_once_with(4, 1)


def test_on_message_drops_when_queue_full_and_acks(caplog):
    q = queue.Queue(maxsize=1)
    q.put("occupied")
    consumer, _ = _consumer(out_queue=q)
    message = _message(
        json.dumps({"object": {}, "time": "t"}).encode(), mid=99, qos=1
    )

    with caplog.at_level("ERROR"):
        consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 1
    assert "cheia" in caplog.text
    consumer.client.ack.assert_called_once_with(99, 1)


def test_ack_delegates_to_client():
    consumer, _ = _consumer()

    consumer.ack(5, 1)

    consumer.client.ack.assert_called_once_with(5, 1)


def test_ack_never_raises_when_client_fails(caplog):
    consumer, _ = _consumer()
    consumer.client.ack.side_effect = RuntimeError("sem conexão")

    with caplog.at_level("ERROR"):
        consumer.ack(5, 1)

    assert "mid=5" in caplog.text


def test_start_configures_manual_ack_and_persistent_session(monkeypatch):
    consumer, _ = _consumer(client_id="linx-routing")
    fake_client = MagicMock()
    factory = MagicMock(return_value=fake_client)
    monkeypatch.setattr(consumer_module.mqtt, "Client", factory)

    assert consumer.start() is True

    _, kwargs = factory.call_args
    assert kwargs["client_id"] == "linx-routing"
    assert kwargs["clean_session"] is False
    assert kwargs["manual_ack"] is True
    fake_client.connect.assert_called_once_with("h", 1883)
    fake_client.loop_forever.assert_called_once()


def test_start_retries_connect_until_success(monkeypatch):
    monkeypatch.setattr("routing.consumer.time.sleep", lambda *_: None)
    consumer, _ = _consumer()
    fake_client = MagicMock()
    attempts = {"n": 0}

    def connect(host, port):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise OSError("broker indisponível")

    fake_client.connect.side_effect = connect
    monkeypatch.setattr(
        consumer_module.mqtt, "Client", MagicMock(return_value=fake_client)
    )

    assert consumer.start() is True
    assert attempts["n"] == 2
    fake_client.loop_forever.assert_called_once()


def test_start_gives_up_after_max_connect_attempts(monkeypatch, caplog):
    monkeypatch.setattr("routing.consumer.time.sleep", lambda *_: None)
    consumer, _ = _consumer(connect_max_attempts=3)
    fake_client = MagicMock()
    fake_client.connect.side_effect = OSError("broker indisponível")
    monkeypatch.setattr(
        consumer_module.mqtt, "Client", MagicMock(return_value=fake_client)
    )

    with caplog.at_level("ERROR"):
        assert consumer.start() is False

    assert fake_client.connect.call_count == 3
    fake_client.loop_forever.assert_not_called()


def test_connect_stops_early_when_stop_event_set(monkeypatch):
    monkeypatch.setattr("routing.consumer.time.sleep", lambda *_: None)
    stop_event = threading.Event()
    stop_event.set()
    consumer, _ = _consumer(stop_event=stop_event)

    assert consumer._connect() is False
    consumer.client.connect.assert_not_called()


def test_stop_disconnects_and_stops_loop():
    consumer, _ = _consumer()

    consumer.stop()

    consumer.client.disconnect.assert_called_once()
    consumer.client.loop_stop.assert_called_once()


def test_stop_is_noop_when_client_never_started():
    q = queue.Queue()
    consumer = MqttConsumer(
        broker_host="h",
        broker_port=1883,
        topic="application/+/device/+/event/up",
        qos=1,
        max_payload_bytes=65536,
        out_queue=q,
    )

    consumer.stop()
