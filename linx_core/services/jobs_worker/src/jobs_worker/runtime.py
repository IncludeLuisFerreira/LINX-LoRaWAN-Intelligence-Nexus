import logging
import threading
from collections.abc import Callable
from typing import Any

import pika
from linx_shared.jobs.broker import JobPublisher
from linx_shared.jobs.handlers import HandlerRegistry
from linx_shared.jobs.outbox import relay_pending_outbox
from sqlalchemy.orm import Session

from jobs_worker.handlers.provision_application import (
    ProvisionApplicationHandler,
)

logger = logging.getLogger(__name__)


def run_outbox_relay(
    stop_event: threading.Event,
    session_factory: Callable[[], Session],
    publisher: JobPublisher,
    poll_interval: float = 1.0,
) -> None:
    while not stop_event.is_set():
        session = session_factory()
        try:
            relay_pending_outbox(session, publisher)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("outbox relay iteration failed")
        finally:
            session.close()
        stop_event.wait(poll_interval)


def run_consumer(
    queue: str,
    callback: Callable[[bytes], None],
    url: str,
    prefetch: int,
    stop_event: threading.Event | None = None,
) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(url))
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_qos(prefetch_count=prefetch)

    def on_message(
        channel: Any,
        method: Any,
        properties: Any,
        body: bytes,
    ) -> None:
        try:
            callback(body)
        except Exception:
            logger.exception("consumer failed to process message")
            channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True,
            )
        else:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(
        queue=queue,
        on_message_callback=on_message,
        auto_ack=False,
    )

    try:
        while stop_event is None or not stop_event.is_set():
            connection.process_data_events(time_limit=1)
    finally:
        channel.close()
        connection.close()


def build_registry() -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register(ProvisionApplicationHandler())
    return registry
