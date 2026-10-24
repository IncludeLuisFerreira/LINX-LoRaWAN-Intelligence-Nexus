import json
from typing import Any, Protocol

import pika

from linx_shared.jobs.constants import (
    JOB_DLX,
    JOB_EVENTS_EXCHANGE,
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_DEAD,
    PROVISIONING_DLQ,
    PROVISIONING_QUEUE,
    PROVISIONING_REQUESTED,
    PROVISIONING_STATUS_QUEUE,
)


class JobPublisher(Protocol):
    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
        *,
        message_id: str | None = None,
    ) -> None: ...


def declare_topology(channel: Any) -> None:
    channel.exchange_declare(
        exchange=JOB_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare(
        exchange=JOB_DLX,
        exchange_type="direct",
        durable=True,
    )
    channel.exchange_declare(
        exchange=JOB_EVENTS_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )

    channel.queue_declare(
        queue=PROVISIONING_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": JOB_DLX,
            "x-dead-letter-routing-key": PROVISIONING_DEAD,
        },
    )
    channel.queue_bind(
        queue=PROVISIONING_QUEUE,
        exchange=JOB_EXCHANGE,
        routing_key=PROVISIONING_REQUESTED,
    )

    channel.queue_declare(
        queue=PROVISIONING_DLQ,
        durable=True,
    )
    channel.queue_bind(
        queue=PROVISIONING_DLQ,
        exchange=JOB_DLX,
        routing_key=PROVISIONING_DEAD,
    )

    channel.queue_declare(
        queue=PROVISIONING_STATUS_QUEUE,
        durable=True,
    )
    channel.queue_bind(
        queue=PROVISIONING_STATUS_QUEUE,
        exchange=JOB_EVENTS_EXCHANGE,
        routing_key=f"{JOB_TYPE_PROVISION_APPLICATION}.#",
    )


class RabbitMQPublisher:
    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: Any = None
        self._channel: Any = None

    @staticmethod
    def _is_open(client: Any) -> bool:
        return bool(getattr(client, "is_open", False))

    def _connect(self) -> Any:
        if (
            self._connection is None
            or self._channel is None
            or not self._is_open(self._connection)
            or not self._is_open(self._channel)
        ):
            self._reset()
            self._connection = pika.BlockingConnection(
                pika.URLParameters(self._url)
            )
            self._channel = self._connection.channel()
        return self._channel

    def _reset(self) -> None:
        connection = self._connection
        self._connection = None
        self._channel = None
        if connection is not None and self._is_open(connection):
            try:
                connection.close()
            except pika.exceptions.AMQPError:
                pass

    def _publish_once(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        properties: Any,
    ) -> None:
        channel = self._connect()
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=properties,
        )

    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
        *,
        message_id: str | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        properties = pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
            message_id=message_id,
        )
        try:
            self._publish_once(exchange, routing_key, body, properties)
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
        ):
            self._reset()
            self._publish_once(exchange, routing_key, body, properties)

    def close(self) -> None:
        self._reset()
