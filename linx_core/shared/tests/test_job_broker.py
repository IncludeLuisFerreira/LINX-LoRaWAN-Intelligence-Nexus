import json

import pika

from linx_shared.jobs import broker
from linx_shared.jobs.broker import (
    RabbitMQPublisher,
    declare_topology,
)
from linx_shared.jobs.constants import (
    JOB_DLX,
    JOB_EVENTS_EXCHANGE,
    JOB_EXCHANGE,
    PROVISIONING_DEAD,
    PROVISIONING_DLQ,
    PROVISIONING_QUEUE,
    PROVISIONING_REQUESTED,
    PROVISIONING_STATUS_QUEUE,
)


class FakeChannel:
    def __init__(self) -> None:
        self.exchanges: list[dict] = []
        self.queues: list[dict] = []
        self.bindings: list[dict] = []
        self.published: list[dict] = []
        self.is_open = True

    def exchange_declare(self, **kwargs) -> None:
        self.exchanges.append(kwargs)

    def queue_declare(self, **kwargs) -> None:
        self.queues.append(kwargs)

    def queue_bind(self, **kwargs) -> None:
        self.bindings.append(kwargs)

    def basic_publish(self, **kwargs) -> None:
        self.published.append(kwargs)


class FakeConnection:
    def __init__(self, channel: FakeChannel) -> None:
        self._channel = channel
        self.closed = False
        self.is_open = True

    def channel(self) -> FakeChannel:
        return self._channel

    def close(self) -> None:
        if not self.is_open:
            raise pika.exceptions.ConnectionWrongStateError("closed")
        self.is_open = False
        self.closed = True


def test_declare_topology_declares_exchanges_queues_and_bindings():
    channel = FakeChannel()

    declare_topology(channel)

    exchanges = {
        item["exchange"]: item["exchange_type"] for item in channel.exchanges
    }
    assert exchanges == {
        JOB_EXCHANGE: "topic",
        JOB_DLX: "direct",
        JOB_EVENTS_EXCHANGE: "topic",
    }
    assert all(item["durable"] is True for item in channel.exchanges)

    queues = {item["queue"]: item for item in channel.queues}
    assert set(queues) == {
        PROVISIONING_QUEUE,
        PROVISIONING_DLQ,
        PROVISIONING_STATUS_QUEUE,
    }
    assert all(item["durable"] is True for item in channel.queues)

    bindings = {
        (item["queue"], item["exchange"], item["routing_key"])
        for item in channel.bindings
    }
    assert bindings == {
        (PROVISIONING_QUEUE, JOB_EXCHANGE, PROVISIONING_REQUESTED),
        (PROVISIONING_DLQ, JOB_DLX, PROVISIONING_DEAD),
        (
            PROVISIONING_STATUS_QUEUE,
            JOB_EVENTS_EXCHANGE,
            "provisioning.application.#",
        ),
    }


def test_declare_topology_configures_main_queue_dlx():
    channel = FakeChannel()

    declare_topology(channel)

    main_queue = next(
        item for item in channel.queues if item["queue"] == PROVISIONING_QUEUE
    )
    assert main_queue["arguments"] == {
        "x-dead-letter-exchange": JOB_DLX,
        "x-dead-letter-routing-key": PROVISIONING_DEAD,
    }


def test_publish_sets_persistent_message_and_message_id(monkeypatch):
    channel = FakeChannel()
    connection = FakeConnection(channel)
    monkeypatch.setattr(
        broker.pika,
        "BlockingConnection",
        lambda parameters: connection,
    )
    publisher = RabbitMQPublisher("amqp://guest:guest@localhost:5672/")
    payload = {"job_id": "job-1", "attempt": 1}

    publisher.publish(
        JOB_EXCHANGE,
        PROVISIONING_REQUESTED,
        payload,
        message_id="job-1",
    )

    published = channel.published[0]
    assert published["exchange"] == JOB_EXCHANGE
    assert published["routing_key"] == PROVISIONING_REQUESTED
    assert json.loads(published["body"]) == payload
    assert published["properties"].delivery_mode == 2
    assert published["properties"].content_type == "application/json"
    assert published["properties"].message_id == "job-1"


class FailingChannel(FakeChannel):
    def basic_publish(self, **kwargs) -> None:
        raise pika.exceptions.AMQPConnectionError("connection lost")


class CloseRaisesConnection(FakeConnection):
    def close(self) -> None:
        self.closed = True
        raise pika.exceptions.ConnectionWrongStateError("already closed")


def test_publish_reconnects_once_on_connection_error(monkeypatch):
    first_channel = FailingChannel()
    first_connection = CloseRaisesConnection(first_channel)
    second_channel = FakeChannel()
    second_connection = FakeConnection(second_channel)
    connections = iter([first_connection, second_connection])
    monkeypatch.setattr(
        broker.pika,
        "BlockingConnection",
        lambda parameters: next(connections),
    )
    publisher = RabbitMQPublisher("amqp://guest:guest@localhost:5672/")

    publisher.publish(
        JOB_EXCHANGE,
        PROVISIONING_REQUESTED,
        {"job_id": "job-1"},
        message_id="job-1",
    )

    assert len(second_channel.published) == 1
    assert publisher._channel is second_channel
    assert publisher._connection is second_connection


def test_publish_replaces_closed_cached_connection(monkeypatch):
    first_channel = FakeChannel()
    first_connection = FakeConnection(first_channel)
    second_channel = FakeChannel()
    second_connection = FakeConnection(second_channel)
    connections = iter([first_connection, second_connection])
    monkeypatch.setattr(
        broker.pika,
        "BlockingConnection",
        lambda parameters: next(connections),
    )
    publisher = RabbitMQPublisher("amqp://guest:guest@localhost:5672/")
    publisher.publish(
        JOB_EXCHANGE,
        PROVISIONING_REQUESTED,
        {"job_id": "job-1"},
    )
    first_connection.is_open = False

    publisher.publish(
        JOB_EXCHANGE,
        PROVISIONING_REQUESTED,
        {"job_id": "job-2"},
    )

    assert first_connection.closed is False
    assert len(second_channel.published) == 1
    assert publisher._channel is second_channel
