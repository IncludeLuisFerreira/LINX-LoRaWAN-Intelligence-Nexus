import logging
import signal
import threading
import time
from types import FrameType
from typing import Any

import pika
from linx_shared.db.base import SessionLocal, engine
from linx_shared.jobs.broker import (
    RabbitMQPublisher,
    declare_topology,
)
from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_QUEUE,
    PROVISIONING_STATUS_QUEUE,
    RETRY_DELAYS_SECONDS,
)
from linx_shared.jobs.envelope import JobEnvelope, JobStatusEvent
from pydantic import ValidationError
from sqlalchemy import text

from jobs_worker.config import WorkerSettings
from jobs_worker.health import check
from jobs_worker.processor import JobProcessor
from jobs_worker.reaper import JobReaper
from jobs_worker.runtime import (
    InvalidMessageError,
    build_registry,
    run_consumer,
    run_outbox_relay,
)
from jobs_worker.status import StatusProcessor

logger = logging.getLogger(__name__)

READY_ATTEMPTS = 30
READY_DELAY_SECONDS = 2
OUTBOX_POLL_SECONDS = 1.0


def _wait_for_dependencies() -> None:
    last_error: Exception | None = None
    for attempt in range(1, READY_ATTEMPTS + 1):
        try:
            check()
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM jobs LIMIT 1"))
            logger.info("dependencies ready after %s attempt(s)", attempt)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "dependencies not ready (attempt %s/%s): %s",
                attempt,
                READY_ATTEMPTS,
                exc,
            )
            if attempt < READY_ATTEMPTS:
                time.sleep(READY_DELAY_SECONDS)
    raise RuntimeError("dependencies did not become ready") from last_error


def _declare_topology(url: str, queue: str) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(url))
    try:
        declare_topology(connection.channel(), queue)
    finally:
        connection.close()


def _parse_envelope(body: bytes) -> JobEnvelope:
    try:
        return JobEnvelope.model_validate_json(body)
    except ValidationError as exc:
        raise InvalidMessageError("invalid job envelope") from exc


def _parse_status_event(body: bytes) -> JobStatusEvent:
    try:
        return JobStatusEvent.model_validate_json(body)
    except ValidationError as exc:
        raise InvalidMessageError("invalid status event") from exc


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = WorkerSettings()
    _wait_for_dependencies()
    queue = settings.worker_queue or PROVISIONING_QUEUE
    _declare_topology(settings.rabbitmq_amqp_url, queue)

    publisher = RabbitMQPublisher(settings.rabbitmq_amqp_url)
    registry = build_registry()
    processor = JobProcessor(
        SessionLocal,
        registry,
        lock_seconds=settings.job_lock_seconds,
        retry_delays=RETRY_DELAYS_SECONDS,
    )
    status_processor = StatusProcessor(SessionLocal)
    reaper = JobReaper(
        SessionLocal,
        interval_seconds=settings.job_reaper_interval_seconds,
    )
    stop_event = threading.Event()

    def job_callback(body: bytes) -> None:
        processor.process(_parse_envelope(body))

    def status_callback(body: bytes) -> None:
        status_processor.process(_parse_status_event(body))

    def declare(channel: Any) -> None:
        declare_topology(channel, queue)

    threads = [
        threading.Thread(
            target=run_outbox_relay,
            args=(
                stop_event,
                SessionLocal,
                publisher,
                OUTBOX_POLL_SECONDS,
                settings.outbox_max_attempts,
            ),
            name="outbox-relay",
            daemon=True,
        ),
        threading.Thread(
            target=reaper.run_forever,
            args=(stop_event,),
            name="job-reaper",
            daemon=True,
        ),
        threading.Thread(
            target=run_consumer,
            args=(
                PROVISIONING_STATUS_QUEUE,
                status_callback,
                settings.rabbitmq_amqp_url,
                settings.worker_prefetch,
                stop_event,
            ),
            kwargs={"declare": declare},
            name="status-consumer",
            daemon=True,
        ),
    ]
    for index in range(settings.worker_concurrency):
        threads.append(
            threading.Thread(
                target=run_consumer,
                args=(
                    queue,
                    job_callback,
                    settings.rabbitmq_amqp_url,
                    settings.worker_prefetch,
                    stop_event,
                ),
                kwargs={"declare": declare},
                name=f"provisioning-consumer-{index}",
                daemon=True,
            )
        )

    def _stop(signum: int, frame: FrameType | None) -> None:
        logger.info("received signal %s, stopping", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info(
        "jobs worker started (queue=%s concurrency=%s job_type=%s)",
        settings.worker_queue,
        settings.worker_concurrency,
        JOB_TYPE_PROVISION_APPLICATION,
    )
    for thread in threads:
        thread.start()

    while not stop_event.is_set():
        stop_event.wait(1.0)

    for thread in threads:
        thread.join(timeout=5.0)
    publisher.close()
    logger.info("jobs worker stopped")


if __name__ == "__main__":
    main()
