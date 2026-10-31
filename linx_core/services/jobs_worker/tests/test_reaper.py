from datetime import datetime, timedelta, timezone

from linx_shared.jobs.constants import (
    JOB_EVENTS_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_REQUESTED,
    JobStatus,
)
from linx_shared.models.job_outbox import JobOutbox
from sqlalchemy import select

from jobs_worker.reaper import JobReaper


def _outbox(db_session, job_id):
    db_session.expire_all()
    return db_session.scalars(
        select(JobOutbox).where(JobOutbox.job_id == job_id)
    ).all()


def test_expired_lease_creates_retry_event_and_command(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(
        status=JobStatus.RUNNING.value,
        attempts=1,
        locked_until=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    reaper = JobReaper(session_factory, interval_seconds=60)

    reaper.run_once()

    rows = _outbox(db_session, job.id)
    by_key = {row.routing_key: row for row in rows}
    retry_key = f"{JOB_TYPE_PROVISION_APPLICATION}.retry"
    assert retry_key in by_key
    assert PROVISIONING_REQUESTED in by_key
    assert by_key[retry_key].exchange == JOB_EVENTS_EXCHANGE
    assert by_key[retry_key].payload["status"] == JobStatus.PENDING.value
    assert by_key[PROVISIONING_REQUESTED].exchange == job.command_exchange

    db_session.expire_all()
    assert job.locked_until is None
    assert job.next_attempt_at is not None
    assert job.status == JobStatus.RUNNING.value


def test_valid_lease_is_left_untouched(
    session_factory, db_session, job_factory
):
    job = job_factory(
        status=JobStatus.RUNNING.value,
        attempts=1,
        locked_until=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    reaper = JobReaper(session_factory, interval_seconds=60)

    reaper.run_once()

    assert _outbox(db_session, job.id) == []
    db_session.expire_all()
    assert job.locked_until is not None


def test_reaper_is_idempotent_when_run_twice(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(
        status=JobStatus.RUNNING.value,
        attempts=1,
        locked_until=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    reaper = JobReaper(session_factory, interval_seconds=60)

    reaper.run_once()
    first_rows = _outbox(db_session, job.id)
    reaper.run_once()
    second_rows = _outbox(db_session, job.id)

    assert len(first_rows) == 2
    assert len(second_rows) == 2
