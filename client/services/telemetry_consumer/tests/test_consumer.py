import asyncio
import json
import threading

import telemetry_consumer.consumer as consumer_module
from telemetry_consumer.config import ConsumerSettings
from telemetry_consumer.consumer import RabbitConsumer


class FakeMessage:
    def __init__(self, body):
        self.body = body
        self.acked = False
        self.rejected = False

    def ack(self):
        self.acked = True


class FakeChannel:
    def __init__(self):
        self.published = []

    def basic_publish(self, body, exchange, routing_key):
        self.published.append((body, exchange, routing_key))


class NackChannel(FakeChannel):
    def basic_publish(self, body, exchange, routing_key):
        self.published.append((body, exchange, routing_key))
        return False


class RaisingChannel(FakeChannel):
    def basic_publish(self, body, exchange, routing_key):
        self.published.append((body, exchange, routing_key))
        raise RuntimeError("dlq down")


async def _ok(envelope):
    return True


async def _always_fail(envelope):
    raise RuntimeError("db down")


VALID_ENVELOPE = {
    "app_id": "app-1",
    "dev_eui": "dev-1",
    "event_type": "up",
    "payload": {"temperature": 21.5},
    "timestamp": "2026-10-08T12:00:00Z",
}


def test_valid_envelope_is_acked():
    settings = ConsumerSettings(app_id="app-1", consumer_max_retries=1)
    consumer = RabbitConsumer(settings, None, _ok, channel=FakeChannel())
    message = FakeMessage(json.dumps(VALID_ENVELOPE).encode())
    consumer._handle_message(message)
    assert message.acked is True
    assert consumer.health()["processed"] == 1


def test_partial_envelope_goes_to_dlq_and_acks():
    channel = FakeChannel()
    settings = ConsumerSettings(app_id="app-1")
    consumer = RabbitConsumer(settings, None, _ok, channel=channel)
    message = FakeMessage(json.dumps({"app_id": "app-1"}).encode())
    consumer._handle_message(message)
    assert message.acked is True
    assert channel.published[0][2] == "linx.telemetry.app-1.dlq"
    assert consumer.health()["failed"] == 1


def test_retry_exhausted_goes_to_dlq_and_acks():
    channel = FakeChannel()
    settings = ConsumerSettings(app_id="app-1", consumer_max_retries=2)
    consumer = RabbitConsumer(settings, None, _always_fail, channel=channel)
    message = FakeMessage(json.dumps(VALID_ENVELOPE).encode())
    consumer._handle_message(message)
    assert message.acked is True
    assert channel.published[0][2] == "linx.telemetry.app-1.dlq"
    assert consumer.health()["failed"] == 1


def test_retry_count_is_initial_plus_max_retries():
    calls = {"n": 0}

    async def _fail(envelope):
        calls["n"] += 1
        raise RuntimeError("db down")

    settings = ConsumerSettings(
        app_id="app-1",
        consumer_max_retries=2,
        consumer_retry_backoff_seconds=0.0,
    )
    consumer = RabbitConsumer(settings, None, _fail, channel=FakeChannel())
    consumer._handle_message(FakeMessage(json.dumps(VALID_ENVELOPE).encode()))
    assert calls["n"] == 3


def test_invalid_json_goes_to_dlq_and_acks():
    channel = FakeChannel()
    settings = ConsumerSettings(app_id="app-1")
    consumer = RabbitConsumer(settings, None, _ok, channel=channel)
    message = FakeMessage(b"not-json")
    consumer._handle_message(message)
    assert message.acked is True
    assert channel.published[0][2] == "linx.telemetry.app-1.dlq"


class FakeConnection:
    def __init__(self, url):
        self.url = url
        self.closed = False

    def channel(self):
        return FakeRealChannel()

    def close(self):
        self.closed = True


class FakeRealChannel:
    def __init__(self):
        self.closed = False
        self.confirms = False

    def enable_publisher_confirms(self):
        self.confirms = True


class FakeExchange:
    def __init__(self, channel, name, exchange_type=None, durable=False):
        self.channel = channel
        self.name = name
        self.exchange_type = exchange_type
        self.durable = durable
        self.declared = False

    def declare(self):
        self.declared = True


class FakeQueue:
    def __init__(self, channel, name, durable=False, auto_delete=False):
        self.channel = channel
        self.name = name
        self.declared = False
        self.bound = None
        self.stop_called = False
        self.messages = []

    def declare(self):
        self.declared = True

    def bind(self, exchange, routing_key=None):
        self.bound = (exchange, routing_key)

    def consume(self, no_ack=False, prefetch=None):
        for message in self.messages:
            yield message

    def stop_consuming(self):
        self.stop_called = True


def test_open_declares_topology(monkeypatch):
    monkeypatch.setattr(consumer_module.rabbitpy, "Connection", FakeConnection)
    monkeypatch.setattr(consumer_module.rabbitpy, "Exchange", FakeExchange)
    monkeypatch.setattr(consumer_module.rabbitpy, "Queue", FakeQueue)
    settings = ConsumerSettings(app_id="app-1")
    consumer = RabbitConsumer(settings, None, _ok)
    consumer._open()
    assert consumer._is_connected() is True
    assert consumer._exchange.declared is True
    assert consumer._queue.declared is True
    assert consumer._dlq.declared is True
    assert consumer._queue.bound[1] == "application.app-1.#"
    assert consumer._dlq.name == "linx.telemetry.app-1.dlq"
    assert consumer._channel.confirms is True


def test_connect_retries_then_fails():
    settings = ConsumerSettings(
        app_id="app-1",
        rabbit_connect_max_attempts=2,
        rabbit_connect_backoff_seconds=0.0,
    )
    consumer = RabbitConsumer(settings, None, _ok)

    def boom():
        raise RuntimeError("no broker")

    consumer._open = boom
    assert consumer.connect() is False


def test_connect_succeeds(monkeypatch):
    monkeypatch.setattr(consumer_module.rabbitpy, "Connection", FakeConnection)
    monkeypatch.setattr(consumer_module.rabbitpy, "Exchange", FakeExchange)
    monkeypatch.setattr(consumer_module.rabbitpy, "Queue", FakeQueue)
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)
    assert consumer.connect() is True


def test_run_consumes_and_stops():
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)
    consumer._connection = FakeConnection("url")
    consumer._channel = FakeRealChannel()
    queue = FakeQueue(consumer._channel, consumer._settings.queue_name)
    message = FakeMessage(json.dumps(VALID_ENVELOPE).encode())
    queue.messages = [message]

    original_consume = queue.consume

    def consume(no_ack=False, prefetch=None):
        yield from original_consume(no_ack=no_ack, prefetch=prefetch)
        consumer._stop_event.set()

    queue.consume = consume
    consumer._queue = queue
    consumer._run()
    assert message.acked is True
    assert consumer.health()["processed"] == 1


def test_run_recovers_from_connection_loss():
    consumer = RabbitConsumer(
        ConsumerSettings(app_id="app-1", rabbit_connect_backoff_seconds=0.0),
        None,
        _ok,
    )
    consumer._connection = FakeConnection("url")
    consumer._channel = FakeRealChannel()

    class BadQueue:
        def consume(self, no_ack=False, prefetch=None):
            raise RuntimeError("lost")

    consumer._queue = BadQueue()
    calls = {"n": 0}

    def fake_connect():
        calls["n"] += 1
        consumer._stop_event.set()
        return False

    consumer.connect = fake_connect
    consumer._run()
    assert calls["n"] == 1


def test_stop_signals_and_closes():
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)
    connection = FakeConnection("url")
    queue = FakeQueue(None, "queue")
    consumer._connection = connection
    consumer._queue = queue
    consumer.stop()
    assert consumer._stop_event.is_set() is True
    assert queue.stop_called is True
    assert connection.closed is True


def test_start_spawns_daemon_thread():
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)
    started = threading.Event()

    def fake_run():
        started.set()

    consumer._run = fake_run
    consumer.start()
    assert started.wait(2) is True
    assert consumer._thread is not None
    assert consumer._thread.daemon is True


def test_close_swallows_errors():
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)

    class BadConnection:
        closed = False

        def close(self):
            raise RuntimeError("boom")

    consumer._connection = BadConnection()
    consumer.close()
    assert consumer._connection is None


def test_dead_letter_without_channel_leaves_unacked():
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)
    message = FakeMessage(b"not-json")
    consumer._handle_message(message)
    assert message.acked is False
    assert consumer.health()["last_error"] is not None


def test_dead_letter_nack_leaves_unacked():
    channel = NackChannel()
    consumer = RabbitConsumer(
        ConsumerSettings(app_id="app-1"), None, _ok, channel=channel
    )
    message = FakeMessage(b"not-json")
    consumer._handle_message(message)
    assert message.acked is False
    assert len(channel.published) == 1


def test_dead_letter_publish_error_leaves_unacked():
    channel = RaisingChannel()
    consumer = RabbitConsumer(
        ConsumerSettings(app_id="app-1"), None, _always_fail, channel=channel
    )
    message = FakeMessage(json.dumps(VALID_ENVELOPE).encode())
    consumer._handle_message(message)
    assert message.acked is False
    assert len(channel.published) == 1


def test_parse_rejects_invalid_payloads():
    consumer = RabbitConsumer(ConsumerSettings(app_id="app-1"), None, _ok)
    assert consumer._parse(b"[1, 2]") is None
    assert consumer._parse(b'{"dev_eui": "x"}') is None
    assert consumer._parse(b"not-json") is None
    assert consumer._parse(b'{"app_id": "x"}') is None
    assert consumer._parse(json.dumps(VALID_ENVELOPE).encode()) == (
        VALID_ENVELOPE
    )


def test_handler_runs_on_provided_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        consumer = RabbitConsumer(
            ConsumerSettings(app_id="app-1"),
            loop,
            _ok,
            channel=FakeChannel(),
        )
        message = FakeMessage(json.dumps(VALID_ENVELOPE).encode())
        consumer._handle_message(message)
        assert message.acked is True
        assert consumer.health()["processed"] == 1
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()


def test_handler_timeout_triggers_retry_and_dlq():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def _slow(envelope):
        await asyncio.sleep(0.5)
        return True

    try:
        channel = FakeChannel()
        settings = ConsumerSettings(
            app_id="app-1",
            consumer_max_retries=0,
            consumer_handler_timeout_seconds=0.01,
        )
        consumer = RabbitConsumer(settings, loop, _slow, channel=channel)
        message = FakeMessage(json.dumps(VALID_ENVELOPE).encode())
        consumer._handle_message(message)
        assert channel.published[0][2] == "linx.telemetry.app-1.dlq"
        assert consumer.health()["failed"] == 1
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        loop.close()
