from typing import Any

import pika
import pytest

from telemetry_consumer.pika_compat import Channel, Queue


class Frame:
    def __init__(self, method) -> None:
        self.method = method


class FakePikaChannel:
    def __init__(self, mode: str = "ack") -> None:
        self.is_open = True
        self.mode = mode
        self.close_callback = None
        self.confirm_callback: Any = None
        self.return_callback: Any = None
        self.published: list[dict] = []
        self.cancelled: list[str] = []
        self._tag = 0

    def add_on_close_callback(self, callback) -> None:
        self.close_callback = callback

    def basic_qos(self, **kwargs) -> None:
        pass

    def basic_consume(self, **kwargs) -> str:
        return "consumer-tag"

    def basic_cancel(self, tag: str) -> None:
        self.cancelled.append(tag)

    def confirm_delivery(self, callback) -> None:
        self.confirm_callback = callback

    def add_on_return_callback(self, callback) -> None:
        self.return_callback = callback

    def basic_publish(self, **kwargs) -> None:
        self._tag += 1
        self.published.append(kwargs)
        on_publish = kwargs.get("on_publish")
        if on_publish is not None:
            on_publish(self._tag)
        if self.mode == "return":
            self.return_callback(
                None,
                None,
                kwargs["properties"],
                kwargs["body"],
            )
        if self.mode == "nack":
            method: Any = pika.spec.Basic.Nack(
                delivery_tag=self._tag, multiple=False
            )
        else:
            method = pika.spec.Basic.Ack(
                delivery_tag=self._tag, multiple=False
            )
        self.confirm_callback(Frame(method))


def _channel(mode: str = "ack") -> tuple[FakePikaChannel, Channel]:
    raw = FakePikaChannel(mode)
    channel = Channel(raw, None)
    channel.enable_publisher_confirms()
    return raw, channel


def test_publish_is_confirmed() -> None:
    _, channel = _channel()

    assert channel.basic_publish(b"body", "exchange", "route") is True


def test_publish_unroutable_raises() -> None:
    _, channel = _channel("return")

    with pytest.raises(pika.exceptions.UnroutableError):
        channel.basic_publish(b"body", "exchange", "missing")


def test_publish_nack_raises() -> None:
    _, channel = _channel("nack")

    with pytest.raises(pika.exceptions.NackError):
        channel.basic_publish(b"body", "exchange", "route")


def test_publish_merges_caller_headers() -> None:
    raw, channel = _channel()

    channel._publish(
        b"body",
        "exchange",
        "route",
        properties={"headers": {"trace": "abc"}},
    )

    headers = raw.published[0]["properties"].headers
    assert headers["trace"] == "abc"
    assert headers["x-publish-id"]


def test_consume_raises_when_channel_closes() -> None:
    raw = FakePikaChannel()
    channel = Channel(raw, None)
    queue = Queue(channel, "q")
    generator = queue.consume(no_ack=True)

    raw.is_open = False

    with pytest.raises(ConnectionError, match="fechado"):
        next(generator)
