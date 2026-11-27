import logging
import signal
import threading
import time
from collections.abc import Callable
from types import FrameType
from typing import Any

import pika
from linx_shared.db.base import SessionLocal, engine
from linx_shared.jobs.broker import declare_status_topology
from linx_shared.jobs.consumer import InvalidMessageError, run_consumer
from linx_shared.jobs.envelope import JobStatusEvent
from pydantic import ValidationError
from sqlalchemy import text

from jobs_status_worker.config import StatusWorkerSettings, settings
from jobs_status_worker.health import check
from jobs_status_worker.status import StatusProcessor

logger = logging.getLogger(__name__)

READY_ATTEMPTS = 30
READY_DELAY_SECONDS = 2


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


def _declare_topology(url: str) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(url))
    try:
        declare_status_topology(connection.channel(), settings.status_queue)
    finally:
        connection.close()


def _parse_status_event(body: bytes) -> JobStatusEvent:
    try:
        return JobStatusEvent.model_validate_json(body)
    except ValidationError as exc:
        raise InvalidMessageError("invalid status event") from exc


def build_status_callback(
    processor: StatusProcessor,
) -> Callable[[bytes], None]:
    def callback(body: bytes) -> None:
        processor.process(_parse_status_event(body))

    return callback


def build_consumer_threads(
    settings: StatusWorkerSettings,
    processor: StatusProcessor,
    stop_event: threading.Event,
) -> list[threading.Thread]:
    callback = build_status_callback(processor)
    queue = settings.status_queue

    def declare(channel: Any) -> None:
        declare_status_topology(channel, queue)

    return [
        threading.Thread(
            target=run_consumer,
            args=(
                settings.status_queue,
                callback,
                settings.rabbitmq_amqp_url,
                settings.status_prefetch,
                stop_event,
            ),
            kwargs={"declare": declare},
            name=f"status-consumer-{index}",
            daemon=True,
        )
        for index in range(settings.status_concurrency)
    ]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = StatusWorkerSettings()
    processor = StatusProcessor(SessionLocal)
    _wait_for_dependencies()
    _declare_topology(settings.rabbitmq_amqp_url)

    stop_event = threading.Event()
    threads = build_consumer_threads(settings, processor, stop_event)

    def _stop(signum: int, frame: FrameType | None) -> None:
        logger.info("received signal %s, stopping", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    logger.info(
        "jobs status worker started (queue=%s concurrency=%s)",
        settings.status_queue,
        settings.status_concurrency,
    )
    for thread in threads:
        thread.start()

    while not stop_event.is_set():
        stop_event.wait(1.0)

    for thread in threads:
        thread.join(timeout=5.0)

    logger.info("jobs status worker stopped")


if __name__ == "__main__":
    main()
