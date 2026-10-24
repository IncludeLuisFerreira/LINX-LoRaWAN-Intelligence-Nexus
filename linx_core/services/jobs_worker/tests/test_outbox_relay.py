from datetime import datetime, timedelta, timezone
from uuid import uuid4

from linx_shared.jobs.outbox import (
    OUTBOX_RETRY_DELAY_SECONDS,
    relay_pending_outbox,
)
from linx_shared.models.job_outbox import JobOutbox
from sqlalchemy import select


class FakePublisher:
    def __init__(self, *, error=None) -> None:
        self.error = error
        self.calls: list[tuple] = []

    def publish(self, exchange, routing_key, payload, *, message_id=None):
        self.calls.append((exchange, routing_key, payload, message_id))
        if self.error is not None:
            raise self.error


def _outbox(db_session, outbox_id):
    db_session.expire_all()
    return db_session.scalars(
        select(JobOutbox).where(JobOutbox.id == outbox_id)
    ).one()


def test_pending_row_is_published_and_marked(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    outbox = JobOutbox(
        job_id=job.id,
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": str(job.id)},
    )
    db_session.add(outbox)
    db_session.flush()
    publisher = FakePublisher()
    reference = datetime.now(timezone.utc)
    session = session_factory()

    try:
        published = relay_pending_outbox(
            session,
            publisher,
            now=reference,
        )
        session.commit()
    finally:
        session.close()

    assert published == 1
    assert publisher.calls == [
        (
            "linx.jobs",
            "provisioning.application.requested",
            {"job_id": str(job.id)},
            str(job.id),
        )
    ]
    row = _outbox(db_session, outbox.id)
    assert row.published_at is not None


def test_publisher_failure_increments_attempts_and_schedules_retry(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    outbox = JobOutbox(
        job_id=job.id,
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": str(job.id)},
    )
    db_session.add(outbox)
    db_session.flush()
    publisher = FakePublisher(error=RuntimeError("broker down"))
    reference = datetime.now(timezone.utc)
    session = session_factory()

    try:
        published = relay_pending_outbox(
            session,
            publisher,
            now=reference,
        )
        session.commit()
    finally:
        session.close()

    assert published == 0
    row = _outbox(db_session, outbox.id)
    assert row.published_at is None
    assert row.attempts == 1
    assert row.next_attempt_at == reference + timedelta(
        seconds=OUTBOX_RETRY_DELAY_SECONDS
    )


def test_two_relays_do_not_publish_same_row_twice(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    outbox = JobOutbox(
        job_id=job.id,
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": str(job.id)},
    )
    db_session.add(outbox)
    db_session.flush()
    first_publisher = FakePublisher()
    second_publisher = FakePublisher()
    first_session = session_factory()
    second_session = session_factory()

    try:
        first_published = relay_pending_outbox(
            first_session,
            first_publisher,
        )
        first_session.flush()
        second_published = relay_pending_outbox(
            second_session,
            second_publisher,
        )
        second_session.rollback()
        first_session.commit()
    finally:
        first_session.close()
        second_session.close()

    assert first_published == 1
    assert second_published == 0
    assert len(first_publisher.calls) == 1
    assert second_publisher.calls == []


def test_unrelated_pending_row_is_not_touched(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    outbox = JobOutbox(
        job_id=job.id,
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": str(uuid4())},
        next_attempt_at=future,
    )
    db_session.add(outbox)
    db_session.flush()
    publisher = FakePublisher()
    session = session_factory()

    try:
        published = relay_pending_outbox(session, publisher)
        session.commit()
    finally:
        session.close()

    assert published == 0
    assert publisher.calls == []
    row = _outbox(db_session, outbox.id)
    assert row.published_at is None
