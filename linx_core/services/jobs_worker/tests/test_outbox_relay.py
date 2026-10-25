from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pika
from linx_shared.db.base import engine
from linx_shared.jobs.constants import (
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_REQUESTED,
)
from linx_shared.jobs.outbox import (
    OUTBOX_RETRY_DELAY_SECONDS,
    relay_pending_outbox,
)
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox
from linx_shared.models.tenant import Tenant
from sqlalchemy import delete, select
from sqlalchemy.orm import Session


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
    assert row.last_error is not None
    assert "broker down" in row.last_error
    assert row.next_attempt_at >= reference + timedelta(
        seconds=OUTBOX_RETRY_DELAY_SECONDS
    )
    assert row.next_attempt_at <= reference + timedelta(
        seconds=OUTBOX_RETRY_DELAY_SECONDS * 1.1
    )


def _seed_committed_outbox():
    with Session(engine) as session:
        tenant = Tenant(name=f"tenant-{uuid4()}")
        session.add(tenant)
        session.flush()
        job = Job(
            type=JOB_TYPE_PROVISION_APPLICATION,
            tenant_id=tenant.id,
            subject_id=uuid4(),
            payload={},
            command_exchange=JOB_EXCHANGE,
            command_routing_key=PROVISIONING_REQUESTED,
            deduplication_key=f"test:{uuid4()}",
        )
        session.add(job)
        session.flush()
        session.add(
            JobOutbox(
                job_id=job.id,
                exchange=JOB_EXCHANGE,
                routing_key=PROVISIONING_REQUESTED,
                payload={"job_id": str(job.id)},
            )
        )
        session.commit()
        return tenant.id


def test_two_relays_do_not_publish_same_row_twice():
    tenant_id = None
    first_connection = engine.connect()
    second_connection = engine.connect()
    first_session = Session(bind=first_connection)
    second_session = Session(bind=second_connection)
    first_publisher = FakePublisher()
    second_publisher = FakePublisher()

    try:
        tenant_id = _seed_committed_outbox()

        first_published = relay_pending_outbox(
            first_session,
            first_publisher,
        )
        first_session.flush()
        second_published = relay_pending_outbox(
            second_session,
            second_publisher,
        )

        assert first_published == 1
        assert second_published == 0
        assert len(first_publisher.calls) == 1
        assert second_publisher.calls == []

        first_session.commit()
    finally:
        second_session.close()
        first_session.close()
        second_connection.close()
        first_connection.close()
        if tenant_id is not None:
            with Session(engine) as cleanup:
                cleanup.execute(delete(Tenant).where(Tenant.id == tenant_id))
                cleanup.commit()


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


def test_publisher_nack_keeps_row_pending_and_schedules_retry(
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
    publisher = FakePublisher(error=pika.exceptions.NackError([1]))
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
    assert row.failed_at is None
    assert row.attempts == 1
    assert row.last_error is not None
    assert row.next_attempt_at > reference


def test_exponential_backoff_grows_with_attempts(
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
        attempts=2,
    )
    db_session.add(outbox)
    db_session.flush()
    publisher = FakePublisher(error=RuntimeError("broker down"))
    reference = datetime.now(timezone.utc)
    session = session_factory()

    try:
        relay_pending_outbox(session, publisher, now=reference)
        session.commit()
    finally:
        session.close()

    row = _outbox(db_session, outbox.id)
    assert row.attempts == 3
    assert row.next_attempt_at >= reference + timedelta(seconds=20)
    assert row.next_attempt_at <= reference + timedelta(seconds=22)


def test_outbox_is_quarantined_after_max_attempts(
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
        attempts=2,
    )
    db_session.add(outbox)
    db_session.flush()
    publisher = FakePublisher(error=RuntimeError("broker down"))
    reference = datetime.now(timezone.utc)
    session = session_factory()

    try:
        relay_pending_outbox(
            session,
            publisher,
            now=reference,
            max_attempts=3,
        )
        session.commit()
    finally:
        session.close()

    row = _outbox(db_session, outbox.id)
    assert row.published_at is None
    assert row.failed_at == reference
    assert row.attempts == 3
    assert row.last_error is not None

    retry_session = session_factory()
    healthy = FakePublisher()
    try:
        published = relay_pending_outbox(retry_session, healthy)
        retry_session.commit()
    finally:
        retry_session.close()

    assert published == 0
    assert healthy.calls == []


def test_database_clock_skips_future_row_and_publishes_due_row(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    due = JobOutbox(
        job_id=job.id,
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": str(job.id)},
    )
    pending = JobOutbox(
        job_id=job.id,
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": str(uuid4())},
        next_attempt_at=future,
    )
    db_session.add_all([due, pending])
    db_session.flush()
    publisher = FakePublisher()
    session = session_factory()

    try:
        published = relay_pending_outbox(session, publisher)
        session.commit()
    finally:
        session.close()

    assert published == 1
    assert len(publisher.calls) == 1
    assert _outbox(db_session, due.id).published_at is not None
    assert _outbox(db_session, pending.id).published_at is None
