import pytest

from telemetry_consumer.pika_compat import Channel, Queue


class FakePikaChannel:
    def __init__(self) -> None:
        self.is_open = True
        self.close_callback = None
        self.cancelled: list[str] = []

    def add_on_close_callback(self, callback) -> None:
        self.close_callback = callback

    def basic_qos(self, **kwargs) -> None:
        pass

    def basic_consume(self, **kwargs) -> str:
        return "consumer-tag"

    def basic_cancel(self, tag: str) -> None:
        self.cancelled.append(tag)


def test_consume_raises_when_channel_closes() -> None:
    raw = FakePikaChannel()
    channel = Channel(raw, None)
    queue = Queue(channel, "q")
    generator = queue.consume(no_ack=True)

    raw.is_open = False

    with pytest.raises(ConnectionError, match="fechado"):
        next(generator)
