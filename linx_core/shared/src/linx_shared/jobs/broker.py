import json
import logging
from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Protocol

import pika

from linx_shared.jobs.constants import (
    JOB_DLX,
    JOB_EVENTS_EXCHANGE,
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_QUEUE,
    PROVISIONING_STATUS_QUEUE,
)
from linx_shared.messaging.topology import (
    JOB_TYPE_TOPOLOGIES,
    JobTypeTopology,
    topologies_for,
)

logger = logging.getLogger(__name__)


class JobPublisher(Protocol):
    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
        *,
        message_id: str | None = None,
    ) -> None: ...


def _resolve_topologies(
    job_types: Sequence[str] | None,
) -> tuple[JobTypeTopology, ...]:
    if job_types is None:
        return JOB_TYPE_TOPOLOGIES
    return topologies_for(job_types)


def _apply_command_queue_override(
    topologies: tuple[JobTypeTopology, ...],
    queue: str,
) -> tuple[JobTypeTopology, ...]:
    if queue == PROVISIONING_QUEUE:
        return topologies
    if not any(
        item.job_type == JOB_TYPE_PROVISION_APPLICATION for item in topologies
    ):
        raise ValueError(
            "override de fila exige o tipo "
            f"{JOB_TYPE_PROVISION_APPLICATION}"
        )
    return tuple(
        (
            replace(item, command_queue=queue)
            if item.job_type == JOB_TYPE_PROVISION_APPLICATION
            else item
        )
        for item in topologies
    )


def declare_status_topology(
    channel: Any,
    queue: str = PROVISIONING_STATUS_QUEUE,
    job_types: Sequence[str] | None = None,
) -> None:
    """Declara apenas a topologia consumida pelo status worker.

    Declara a exchange de eventos e uma binding ``<tipo>.#`` por tipo. A fila
    é declarada sem DLX para não conflitar (406) com uma declaração anterior
    que tenha argumentos diferentes.
    """
    topologies = _resolve_topologies(job_types)
    channel.exchange_declare(
        exchange=JOB_EVENTS_EXCHANGE,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(
        queue=queue,
        durable=True,
    )
    for topology in topologies:
        channel.queue_bind(
            queue=queue,
            exchange=JOB_EVENTS_EXCHANGE,
            routing_key=topology.status_binding,
        )


def declare_topology(
    channel: Any,
    queue: str = PROVISIONING_QUEUE,
    job_types: Sequence[str] | None = None,
) -> None:
    topologies = _apply_command_queue_override(
        _resolve_topologies(job_types),
        queue,
    )
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

    for topology in topologies:
        channel.queue_declare(
            queue=topology.command_queue,
            durable=True,
            arguments={
                "x-dead-letter-exchange": JOB_DLX,
                "x-dead-letter-routing-key": topology.dead_routing_key,
            },
        )
        channel.queue_bind(
            queue=topology.command_queue,
            exchange=JOB_EXCHANGE,
            routing_key=topology.requested_routing_key,
        )

        channel.queue_declare(
            queue=topology.dead_letter_queue,
            durable=True,
        )
        channel.queue_bind(
            queue=topology.dead_letter_queue,
            exchange=JOB_DLX,
            routing_key=topology.dead_routing_key,
        )

    declare_status_topology(
        channel,
        job_types=tuple(item.job_type for item in topologies),
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
            self._channel.confirm_delivery()
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
            mandatory=True,
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
            pika.exceptions.UnroutableError,
            pika.exceptions.NackError,
        ):
            logger.error(
                "broker did not confirm message exchange=%s routing_key=%s "
                "message_id=%s",
                exchange,
                routing_key,
                message_id,
            )
            raise
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
        ):
            self._reset()
            self._publish_once(exchange, routing_key, body, properties)

    def close(self) -> None:
        self._reset()
