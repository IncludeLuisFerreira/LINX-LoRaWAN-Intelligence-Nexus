import json

import pika
import pytest

from linx_shared.jobs import broker
from linx_shared.jobs.broker import (
    RabbitMQPublisher,
    declare_status_topology,
    declare_topology,
)
from linx_shared.jobs.constants import (
    JOB_DLX,
    JOB_EVENTS_EXCHANGE,
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_DEAD,
    PROVISIONING_DLQ,
    PROVISIONING_QUEUE,
    PROVISIONING_REQUESTED,
    PROVISIONING_STATUS_DEAD,
    PROVISIONING_STATUS_DLQ,
    PROVISIONING_STATUS_QUEUE,
)


class FakeChannel:
    def __init__(self) -> None:
        self.exchanges: list[dict] = []
        self.queues: list[dict] = []
        self.bindings: list[dict] = []
        self.published: list[dict] = []
        self.confirm_calls = 0
        self.is_open = True

    def confirm_delivery(self) -> None:
        self.confirm_calls += 1

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
        PROVISIONING_STATUS_DLQ,
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
        (
            PROVISIONING_STATUS_DLQ,
            JOB_DLX,
            PROVISIONING_STATUS_DEAD,
        ),
    }


def _assert_only_status_topology(channel, queue):
    assert [item["exchange"] for item in channel.exchanges] == [
        JOB_EVENTS_EXCHANGE
    ]
    assert channel.exchanges[0]["exchange_type"] == "topic"
    assert channel.exchanges[0]["durable"] is True

    assert [item["queue"] for item in channel.queues] == [
        queue,
        PROVISIONING_STATUS_DLQ,
    ]
    status_queue = channel.queues[0]
    assert status_queue["durable"] is True
    assert status_queue["arguments"] == {
        "x-dead-letter-exchange": JOB_DLX,
        "x-dead-letter-routing-key": PROVISIONING_STATUS_DEAD,
    }
    assert channel.queues[1]["durable"] is True

    assert {
        (
            item["queue"],
            item["exchange"],
            item["routing_key"],
        )
        for item in channel.bindings
    } == {
        (
            queue,
            JOB_EVENTS_EXCHANGE,
            "provisioning.application.#",
        ),
        (
            PROVISIONING_STATUS_DLQ,
            JOB_DLX,
            PROVISIONING_STATUS_DEAD,
        ),
    }


def test_declare_status_topology_declares_only_status_queue():
    channel = FakeChannel()

    declare_status_topology(channel)

    _assert_only_status_topology(channel, PROVISIONING_STATUS_QUEUE)


def test_declare_status_topology_uses_custom_queue():
    channel = FakeChannel()

    declare_status_topology(channel, "linx.jobs.status.custom")

    _assert_only_status_topology(channel, "linx.jobs.status.custom")


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
    assert published["mandatory"] is True
    assert channel.confirm_calls == 1


class FailingChannel(FakeChannel):
    def basic_publish(self, **kwargs) -> None:
        raise pika.exceptions.AMQPConnectionError("connection lost")


class NackChannel(FakeChannel):
    def basic_publish(self, **kwargs) -> None:
        raise pika.exceptions.NackError([1])


class UnroutableChannel(FakeChannel):
    def basic_publish(self, **kwargs) -> None:
        raise pika.exceptions.UnroutableError([1])


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


def test_publish_propagates_nack_without_marking_success(monkeypatch):
    channel = NackChannel()
    connection = FakeConnection(channel)
    monkeypatch.setattr(
        broker.pika,
        "BlockingConnection",
        lambda parameters: connection,
    )
    publisher = RabbitMQPublisher("amqp://guest:guest@localhost:5672/")

    with pytest.raises(pika.exceptions.NackError):
        publisher.publish(
            JOB_EXCHANGE, PROVISIONING_REQUESTED, {"job_id": "x"}
        )

    assert channel.published == []
    assert channel.confirm_calls == 1


def test_publish_propagates_unroutable_without_reconnecting(monkeypatch):
    channel = UnroutableChannel()
    connection = FakeConnection(channel)
    connections = [connection]
    monkeypatch.setattr(
        broker.pika,
        "BlockingConnection",
        lambda parameters: connections.pop(0),
    )
    publisher = RabbitMQPublisher("amqp://guest:guest@localhost:5672/")

    with pytest.raises(pika.exceptions.UnroutableError):
        publisher.publish(
            JOB_EXCHANGE, PROVISIONING_REQUESTED, {"job_id": "x"}
        )

    assert channel.confirm_calls == 1


def test_declare_topology_uses_custom_queue():
    channel = FakeChannel()

    declare_topology(channel, "linx.jobs.custom")

    queues = {item["queue"]: item for item in channel.queues}
    assert "linx.jobs.custom" in queues
    assert queues["linx.jobs.custom"]["arguments"] == {
        "x-dead-letter-exchange": JOB_DLX,
        "x-dead-letter-routing-key": PROVISIONING_DEAD,
    }
    assert (
        "linx.jobs.custom",
        JOB_EXCHANGE,
        PROVISIONING_REQUESTED,
    ) in {
        (item["queue"], item["exchange"], item["routing_key"])
        for item in channel.bindings
    }


SECOND_JOB_TYPE = "provisioning.tenant"


def test_declare_topology_declares_second_job_type():
    channel = FakeChannel()

    declare_topology(
        channel,
        job_types=(JOB_TYPE_PROVISION_APPLICATION, SECOND_JOB_TYPE),
    )

    queues = {item["queue"]: item for item in channel.queues}
    assert set(queues) == {
        PROVISIONING_QUEUE,
        PROVISIONING_DLQ,
        PROVISIONING_STATUS_QUEUE,
        PROVISIONING_STATUS_DLQ,
        f"linx.jobs.{SECOND_JOB_TYPE}",
        f"linx.jobs.{SECOND_JOB_TYPE}.dlq",
    }
    assert queues[f"linx.jobs.{SECOND_JOB_TYPE}"]["arguments"] == {
        "x-dead-letter-exchange": JOB_DLX,
        "x-dead-letter-routing-key": f"{SECOND_JOB_TYPE}.dead",
    }

    bindings = {
        (item["queue"], item["exchange"], item["routing_key"])
        for item in channel.bindings
    }
    assert (
        f"linx.jobs.{SECOND_JOB_TYPE}",
        JOB_EXCHANGE,
        f"{SECOND_JOB_TYPE}.requested",
    ) in bindings
    assert (
        f"linx.jobs.{SECOND_JOB_TYPE}.dlq",
        JOB_DLX,
        f"{SECOND_JOB_TYPE}.dead",
    ) in bindings
    assert (
        PROVISIONING_STATUS_QUEUE,
        JOB_EVENTS_EXCHANGE,
        f"{SECOND_JOB_TYPE}.#",
    ) in bindings
    assert (
        PROVISIONING_STATUS_DLQ,
        JOB_DLX,
        PROVISIONING_STATUS_DEAD,
    ) in bindings


def test_declare_status_topology_binds_each_job_type():
    channel = FakeChannel()

    declare_status_topology(
        channel,
        job_types=(JOB_TYPE_PROVISION_APPLICATION, SECOND_JOB_TYPE),
    )

    assert [item["queue"] for item in channel.queues] == [
        PROVISIONING_STATUS_QUEUE,
        PROVISIONING_STATUS_DLQ,
    ]
    assert {
        (item["queue"], item["exchange"], item["routing_key"])
        for item in channel.bindings
    } == {
        (
            PROVISIONING_STATUS_QUEUE,
            JOB_EVENTS_EXCHANGE,
            f"{JOB_TYPE_PROVISION_APPLICATION}.#",
        ),
        (
            PROVISIONING_STATUS_QUEUE,
            JOB_EVENTS_EXCHANGE,
            f"{SECOND_JOB_TYPE}.#",
        ),
        (
            PROVISIONING_STATUS_DLQ,
            JOB_DLX,
            PROVISIONING_STATUS_DEAD,
        ),
    }


def test_declare_topology_rejects_queue_override_without_legacy_type():
    with pytest.raises(ValueError, match="override"):
        declare_topology(
            FakeChannel(),
            "linx.jobs.custom",
            job_types=(SECOND_JOB_TYPE,),
        )


def _topic_matches(pattern: str, key: str) -> bool:
    """Matcher mínimo de topic exchange do RabbitMQ (``*`` e ``#``)."""
    pattern_parts = pattern.split(".")
    key_parts = key.split(".")

    def match(pattern_index: int, key_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return key_index == len(key_parts)
        part = pattern_parts[pattern_index]
        if part == "#":
            return any(
                match(pattern_index + 1, next_index)
                for next_index in range(key_index, len(key_parts) + 1)
            )
        if key_index == len(key_parts):
            return False
        if part == "*" or part == key_parts[key_index]:
            return match(pattern_index + 1, key_index + 1)
        return False

    return match(0, 0)


def _routable(channel, exchange: str, key: str) -> bool:
    return any(
        item["exchange"] == exchange
        and _topic_matches(item["routing_key"], key)
        for item in channel.bindings
    )


def test_second_job_type_events_are_routable():
    channel = FakeChannel()
    declare_topology(
        channel,
        job_types=(JOB_TYPE_PROVISION_APPLICATION, SECOND_JOB_TYPE),
    )

    for job_type in (JOB_TYPE_PROVISION_APPLICATION, SECOND_JOB_TYPE):
        assert _routable(channel, JOB_EXCHANGE, f"{job_type}.requested")
        for suffix in ("started", "succeeded", "failed", "retry"):
            assert _routable(
                channel, JOB_EVENTS_EXCHANGE, f"{job_type}.{suffix}"
            )
        assert _routable(channel, JOB_DLX, f"{job_type}.dead")
