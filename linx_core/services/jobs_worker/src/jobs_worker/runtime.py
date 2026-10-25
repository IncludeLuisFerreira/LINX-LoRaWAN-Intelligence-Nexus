import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import pika
from linx_shared.jobs.broker import JobPublisher
from linx_shared.jobs.handlers import HandlerRegistry
from linx_shared.jobs.outbox import (
    OUTBOX_MAX_ATTEMPTS,
    relay_pending_outbox,
)
from sqlalchemy.orm import Session

from jobs_worker.handlers.provision_application import (
    ProvisionApplicationHandler,
)

logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5.0


class InvalidMessageError(Exception):
    """Mensagem inválida/venenosa: não deve voltar para a fila principal."""


def run_outbox_relay(
    stop_event: threading.Event,
    session_factory: Callable[[], Session],
    publisher: JobPublisher,
    poll_interval: float = 1.0,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
) -> None:
    while not stop_event.is_set():
        session = session_factory()
        try:
            relay_pending_outbox(
                session,
                publisher,
                max_attempts=max_attempts,
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("outbox relay iteration failed")
        finally:
            session.close()
        stop_event.wait(poll_interval)


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        logger.debug("failed to close AMQP resource", exc_info=True)


def run_consumer(
    queue: str,
    callback: Callable[[bytes], None],
    url: str,
    prefetch: int,
    stop_event: threading.Event | None = None,
    *,
    declare: Callable[[Any], None] | None = None,
) -> None:
    while stop_event is None or not stop_event.is_set():
        connection: Any = None
        channel: Any = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(url))
            channel = connection.channel()
            if declare is not None:
                declare(channel)
            channel.basic_qos(prefetch_count=prefetch)

            def on_message(
                channel: Any,
                method: Any,
                properties: Any,
                body: bytes,
            ) -> None:
                try:
                    callback(body)
                except InvalidMessageError:
                    logger.exception("discarding invalid message")
                    channel.basic_nack(
                        delivery_tag=method.delivery_tag,
                        requeue=False,
                    )
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

            while stop_event is None or not stop_event.is_set():
                connection.process_data_events(time_limit=1)
        except Exception:
            if stop_event is not None and stop_event.is_set():
                break
            logger.exception("consumer connection failed; reconnecting")
            if stop_event is not None:
                stop_event.wait(RECONNECT_DELAY_SECONDS)
            else:
                time.sleep(RECONNECT_DELAY_SECONDS)
        finally:
            _close_quietly(channel)
            _close_quietly(connection)


def build_registry() -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register(ProvisionApplicationHandler())
    return registry
