import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from routing import publisher as publisher_module
from routing.publisher import RabbitPublisher


class _FakeRabbit:
    def __init__(self):
        self.connection_calls = []
        self.last_message = None
        self.published = []
        self.exchange = None

    def Connection(self, url):
        self.connection_calls.append(url)
        return self._connection()

    def _connection(self):
        conn = MagicMock()
        channel = MagicMock()
        conn.channel.return_value = channel
        self.channel = channel
        return conn

    def Exchange(
        self,
        channel,
        name,
        exchange_type="direct",
        durable=True,
        auto_delete=False,
        arguments=None,
    ):
        self.exchange = SimpleNamespace(
            name=name, exchange_type=exchange_type, durable=durable
        )
        self.exchange.declare = MagicMock()
        return self.exchange

    def Message(self, channel, body, properties=None):
        self.last_message = SimpleNamespace(
            body=body,
            properties=properties,
            publish=MagicMock(return_value=True),
        )
        return self.last_message


@pytest.fixture
def fake_rabbit(monkeypatch):
    fake = _FakeRabbit()
    monkeypatch.setattr(publisher_module, "rabbitpy", fake)
    return fake


def test_connect_declares_durable_topic_exchange(fake_rabbit):
    pub = RabbitPublisher("amqp://h", "linx.telemetry")

    assert pub.connect() is True
    assert fake_rabbit.connection_calls == ["amqp://h"]
    assert fake_rabbit.exchange.name == "linx.telemetry"
    assert fake_rabbit.exchange.exchange_type == "topic"
    assert fake_rabbit.exchange.durable is True
    assert fake_rabbit.channel.enable_publisher_confirms.called


def test_connect_retries_then_succeeds(monkeypatch, fake_rabbit):
    monkeypatch.setattr("routing.publisher.time.sleep", lambda *_: None)
    attempts = {"n": 0}
    real_connection = fake_rabbit.Connection

    def flaky(url):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("offline")
        return real_connection(url)

    fake_rabbit.Connection = flaky
    pub = RabbitPublisher("amqp://h", "linx.telemetry")

    assert pub.connect() is True
    assert attempts["n"] == 3


def test_connect_gives_up_and_returns_false(monkeypatch, fake_rabbit, caplog):
    monkeypatch.setattr("routing.publisher.time.sleep", lambda *_: None)
    fake_rabbit.Connection = MagicMock(side_effect=OSError("offline"))
    pub = RabbitPublisher("amqp://h", "linx.telemetry", connect_max_attempts=2)

    with caplog.at_level("ERROR"):
        assert pub.connect() is False
    assert fake_rabbit.Connection.call_count == 2


def test_connect_closes_partial_connection_on_failure(
    monkeypatch, fake_rabbit, caplog
):
    monkeypatch.setattr("routing.publisher.time.sleep", lambda *_: None)
    conns = []

    def opening_but_flaky(url):
        conn = MagicMock()
        conn.channel.side_effect = OSError("channel boom")
        conns.append(conn)
        return conn

    fake_rabbit.Connection = opening_but_flaky
    pub = RabbitPublisher("amqp://h", "linx.telemetry", connect_max_attempts=2)

    with caplog.at_level("ERROR"):
        assert pub.connect() is False

    assert len(conns) == 2
    for conn in conns:
        conn.close.assert_called()


def test_publish_sends_persistent_json(fake_rabbit):
    pub = RabbitPublisher("amqp://h", "linx.telemetry")
    pub.connect()

    assert pub.publish("application.app1.device.devA.up", {"a": 1}) is True

    msg = fake_rabbit.last_message
    assert json.loads(msg.body) == {"a": 1}
    assert msg.properties["content_type"] == "application/json"
    assert msg.properties["delivery_mode"] == 2
    msg.publish.assert_called_once_with(
        fake_rabbit.exchange, "application.app1.device.devA.up"
    )


def test_publish_returns_false_when_broker_rejects(fake_rabbit, caplog):
    pub = RabbitPublisher("amqp://h", "linx.telemetry")
    pub.connect()
    fake_rabbit.Message = (
        lambda channel, body, properties=None: SimpleNamespace(
            publish=MagicMock(return_value=False)
        )
    )

    with caplog.at_level("ERROR"):
        assert pub.publish("rk", {"a": 1}) is False
