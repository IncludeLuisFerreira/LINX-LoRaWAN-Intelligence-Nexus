from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from linx_shared.jobs.broker import JobPublisher
from linx_shared.models.job_outbox import JobOutbox

OUTBOX_RETRY_DELAY_SECONDS = 5


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def relay_pending_outbox(
    session: Session,
    publisher: JobPublisher,
    *,
    now: datetime | None = None,
    batch_size: int = 50,
) -> int:
    reference = now or _utcnow()
    statement = (
        select(JobOutbox)
        .where(
            JobOutbox.published_at.is_(None),
            JobOutbox.next_attempt_at <= reference,
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
        except Exception:
            row.attempts += 1
            row.next_attempt_at = reference + timedelta(
                seconds=OUTBOX_RETRY_DELAY_SECONDS
            )
        else:
            row.published_at = reference
            published += 1
    return published
