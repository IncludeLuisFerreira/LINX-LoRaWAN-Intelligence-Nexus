import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from linx_shared.jobs.broker import JobPublisher
from linx_shared.models.job_outbox import JobOutbox

logger = logging.getLogger(__name__)

OUTBOX_RETRY_DELAY_SECONDS = 5
OUTBOX_MAX_BACKOFF_SECONDS = 300
OUTBOX_MAX_ATTEMPTS = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_seconds(attempts: int) -> float:
    exponent = max(attempts - 1, 0)
    base = min(
        OUTBOX_RETRY_DELAY_SECONDS * (2**exponent),
        OUTBOX_MAX_BACKOFF_SECONDS,
    )
    return base + random.uniform(0, base * 0.1)


def relay_pending_outbox(
    session: Session,
    publisher: JobPublisher,
    *,
    now: datetime | None = None,
    batch_size: int = 50,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
) -> int:
    reference = (
        now or session.scalar(select(func.clock_timestamp())) or _utcnow()
    )
    due = JobOutbox.next_attempt_at <= (
        now if now is not None else func.clock_timestamp()
    )
    statement = (
        select(JobOutbox)
        .where(
            JobOutbox.published_at.is_(None),
            JobOutbox.failed_at.is_(None),
            due,
        )
        .order_by(JobOutbox.next_attempt_at, JobOutbox.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = session.scalars(statement).all()

    published = 0
    for row in rows:
        try:
            publisher.publish(
                row.exchange,
                row.routing_key,
                row.payload,
                message_id=str(row.job_id),
            )
        except Exception as exc:  # noqa: BLE001
            row.attempts += 1
            row.last_error = f"{exc.__class__.__name__}: {exc}"
            if row.attempts >= max_attempts:
                row.failed_at = reference
                logger.error(
                    "outbox message quarantined after %s attempts "
                    "outbox_id=%s job_id=%s error=%s",
                    row.attempts,
                    row.id,
                    row.job_id,
                    row.last_error,
                )
                continue
            delay = _backoff_seconds(row.attempts)
            row.next_attempt_at = reference + timedelta(seconds=delay)
            logger.warning(
                "outbox publish failed; retrying in %.2fs "
                "outbox_id=%s attempts=%s error=%s",
                delay,
                row.id,
                row.attempts,
                row.last_error,
            )
        else:
            row.published_at = reference
            row.last_error = None
            published += 1
    return published
