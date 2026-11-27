import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import pika
from pydantic import ValidationError

from linx_shared.jobs.broker import RabbitMQPublisher
from linx_shared.jobs.constants import (
    JOB_DLX,
    PROVISIONING_STATUS_DEAD,
    PROVISIONING_STATUS_QUEUE,
)
from linx_shared.jobs.envelope import JobEnvelope
from linx_shared.messaging.policy import (
    FailurePolicy,
    InvalidMessageError,
    ProcessOutcome,
)

__all__ = ["InvalidMessageError", "run_consumer"]

logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5.0

PublisherFactory = Callable[[str], Any]


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        logger.debug("failed to close AMQP resource", exc_info=True)


def _dead_letter_routing_key(
    queue: str,
    body: bytes,
    override: str | None,
) -> str:
    """Escolhe a routing key da DLX para a mensagem que falhou."""
    if override is not None:
        return override
    if queue == PROVISIONING_STATUS_QUEUE:
        return PROVISIONING_STATUS_DEAD
    try:
        envelope = JobEnvelope.model_validate_json(body)
    except ValidationError:
        return PROVISIONING_STATUS_DEAD
    return f"{envelope.type}.dead"


def run_consumer(
    queue: str,
    callback: Callable[[bytes], None],
    url: str,
    prefetch: int,
    stop_event: threading.Event | None = None,
    *,
    declare: Callable[[Any], None] | None = None,
    policy: FailurePolicy | None = None,
    dead_letter_routing_key: str | None = None,
    publisher_factory: PublisherFactory = RabbitMQPublisher,
) -> None:
    failure_policy = policy or FailurePolicy()
    publisher = publisher_factory(url)

    def dead_letter(
        body: bytes,
        message_id: str | None,
    ) -> None:
        routing_key = _dead_letter_routing_key(
            queue,
            body,
            dead_letter_routing_key,
        )
        publisher.publish_raw(
            JOB_DLX,
            routing_key,
            body,
            message_id=message_id,
        )

    try:
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
                    message_id = getattr(properties, "message_id", None)
                    attempt = 0
                    while True:
                        attempt += 1
                        try:
                            callback(body)
                        except Exception as exc:  # noqa: BLE001
                            outcome = failure_policy.decide(exc, attempt)
                            if outcome is ProcessOutcome.RETRY:
                                delay = failure_policy.delay(attempt)
                                logger.warning(
                                    "transient failure; retrying in %.1fs "
                                    "(attempt %s/%s) queue=%s: %s",
                                    delay,
                                    attempt,
                                    failure_policy.max_attempts,
                                    queue,
                                    exc,
                                )
                                if delay > 0:
                                    if stop_event is not None:
                                        if stop_event.wait(delay):
                                            return
                                    else:
                                        time.sleep(delay)
                                continue

                            logger.error(
                                "dead-lettering message after %s "
                                "attempt(s) queue=%s: %s",
                                attempt,
                                queue,
                                exc,
                            )
                            try:
                                dead_letter(body, message_id)
                            except Exception:  # noqa: BLE001
                                logger.exception(
                                    "failed to publish dead letter; "
                                    "requeueing message"
                                )
                                channel.basic_nack(
                                    delivery_tag=method.delivery_tag,
                                    requeue=True,
                                )
                                return
                            channel.basic_ack(delivery_tag=method.delivery_tag)
                            return
                        else:
                            channel.basic_ack(delivery_tag=method.delivery_tag)
                            return

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
    finally:
        _close_quietly(publisher)
