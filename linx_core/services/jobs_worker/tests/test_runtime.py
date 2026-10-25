import threading

from jobs_worker import runtime


class FakeMethod:
    def __init__(self, delivery_tag: int) -> None:
        self.delivery_tag = delivery_tag


class FakeChannel:
    def __init__(self) -> None:
        self.queue_declares: list[dict] = []
        self.qos: list[dict] = []
        self.consumes: list[dict] = []
        self.acks: list[int] = []
        self.nacks: list[tuple[int, bool]] = []
        self.consumer_callback = None
        self.closed = False

    def queue_declare(self, **kwargs) -> None:
        self.queue_declares.append(kwargs)

    def basic_qos(self, **kwargs) -> None:
        self.qos.append(kwargs)

    def basic_consume(self, **kwargs) -> None:
        self.consumes.append(kwargs)
        self.consumer_callback = kwargs["on_message_callback"]

    def basic_ack(self, delivery_tag: int) -> None:
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag: int, requeue: bool) -> None:
        self.nacks.append((delivery_tag, requeue))

    def close(self) -> None:
        self.closed = True


class StoppingConnection:
    def __init__(self, channel: FakeChannel, stop: threading.Event) -> None:
        self._channel = channel
        self._stop = stop
        self.closed = False

    def channel(self) -> FakeChannel:
        return self._channel

    def process_data_events(self, time_limit: int = 1) -> None:
        self._stop.set()

    def close(self) -> None:
        self.closed = True


class FailingConnection(StoppingConnection):
    def process_data_events(self, time_limit: int = 1) -> None:
        raise RuntimeError("broker blip")


def _patch_connection(monkeypatch, connections):
    pending = list(connections)

    def factory(parameters):
        return pending.pop(0)

    monkeypatch.setattr(runtime.pika, "BlockingConnection", factory)


def test_run_consumer_does_not_redeclare_queue(monkeypatch):
    stop = threading.Event()
    channel = FakeChannel()
    connection = StoppingConnection(channel, stop)
    _patch_connection(monkeypatch, [connection])

    runtime.run_consumer(
        "linx.jobs.provisioning",
        lambda body: None,
        "amqp://127.0.0.1:5672/",
        10,
        stop,
    )

    assert channel.queue_declares == []
    assert channel.qos == [{"prefetch_count": 10}]
    assert channel.consumes[0]["queue"] == "linx.jobs.provisioning"
    assert channel.consumes[0]["auto_ack"] is False
    assert channel.closed is True
    assert connection.closed is True


def test_run_consumer_acks_success_and_nacks_failure(monkeypatch):
    stop = threading.Event()
    channel = FakeChannel()
    connection = StoppingConnection(channel, stop)
    _patch_connection(monkeypatch, [connection])

    def callback(body: bytes) -> None:
        if body == b"bad":
            raise RuntimeError("handler failed")

    runtime.run_consumer(
        "linx.jobs.provisioning",
        callback,
        "amqp://127.0.0.1:5672/",
        1,
        stop,
    )

    channel.consumer_callback(channel, FakeMethod(1), None, b"good")
    channel.consumer_callback(channel, FakeMethod(2), None, b"bad")

    assert channel.acks == [1]
    assert channel.nacks == [(2, True)]


def test_run_consumer_reconnects_after_connection_failure(monkeypatch):
    stop = threading.Event()
    first_channel = FakeChannel()
    first = FailingConnection(first_channel, stop)
    second_channel = FakeChannel()
    second = StoppingConnection(second_channel, stop)
    _patch_connection(monkeypatch, [first, second])
    monkeypatch.setattr(runtime, "RECONNECT_DELAY_SECONDS", 0.0)

    runtime.run_consumer(
        "linx.jobs.provisioning",
        lambda body: None,
        "amqp://127.0.0.1:5672/",
        1,
        stop,
    )

    assert first.closed is True
    assert second.closed is True
    assert len(second_channel.consumes) == 1
