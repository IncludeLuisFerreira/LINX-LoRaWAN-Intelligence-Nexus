from datetime import datetime, timezone

from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    JobStatus,
)
from linx_shared.jobs.envelope import JobError, JobStatusEvent

from jobs_worker.status import StatusProcessor


def _event(job, status, *, attempt=None, result=None, error=None):
    return JobStatusEvent(
        job_id=job.id,
        type=job.type,
        status=status,
        attempt=job.attempts if attempt is None else attempt,
        result=result,
        error=error,
        finished_at=(
            datetime.now(timezone.utc)
            if status in (JobStatus.SUCCEEDED, JobStatus.FAILED)
            else None
        ),
    )


def test_started_moves_pending_to_running(
    session_factory, db_session, job_factory
):
    job = job_factory(attempts=1)
    processor = StatusProcessor(session_factory)

    processor.process(_event(job, JobStatus.RUNNING))

    db_session.expire_all()
    assert job.status == JobStatus.RUNNING.value
    assert job.started_at is not None


def test_succeeded_stores_result(session_factory, db_session, job_factory):
    job = job_factory(status=JobStatus.RUNNING.value, attempts=1)
    processor = StatusProcessor(session_factory)

    processor.process(_event(job, JobStatus.SUCCEEDED, result={"port": 8421}))

    db_session.expire_all()
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"port": 8421}
    assert job.finished_at is not None
    assert job.locked_until is None


def test_duplicate_succeeded_is_ignored(
    session_factory, db_session, job_factory
):
    job = job_factory(status=JobStatus.RUNNING.value, attempts=1)
    processor = StatusProcessor(session_factory)
    event = _event(job, JobStatus.SUCCEEDED, result={"port": 8421})

    processor.process(event)
    db_session.expire_all()
    first_finished_at = job.finished_at
    processor.process(event)
    db_session.expire_all()

    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"port": 8421}
    assert job.finished_at == first_finished_at


def test_late_started_does_not_regress_succeeded(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(status=JobStatus.SUCCEEDED.value, attempts=1)
    processor = StatusProcessor(session_factory)

    processor.process(_event(job, JobStatus.RUNNING))

    db_session.expire_all()
    assert job.status == JobStatus.SUCCEEDED.value


def test_older_attempt_event_is_ignored(
    session_factory, db_session, job_factory
):
    job = job_factory(attempts=2)
    processor = StatusProcessor(session_factory)

    processor.process(
        _event(
            job,
            JobStatus.SUCCEEDED,
            attempt=1,
            result={"port": 8421},
        )
    )

    db_session.expire_all()
    assert job.status == JobStatus.PENDING.value
    assert job.result is None


def test_retry_event_moves_job_back_to_pending_with_error(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(status=JobStatus.RUNNING.value, attempts=1)
    processor = StatusProcessor(session_factory)
    next_attempt_at = datetime.now(timezone.utc)
    error = JobError(
        code="unavailable",
        message="temporary",
        retryable=True,
        grpc_code="UNAVAILABLE",
    )
    event = JobStatusEvent(
        job_id=job.id,
        type=JOB_TYPE_PROVISION_APPLICATION,
        status=JobStatus.PENDING,
        attempt=1,
        error=error,
        next_attempt_at=next_attempt_at,
    )

    processor.process(event)

    db_session.expire_all()
    assert job.status == JobStatus.PENDING.value
    assert job.error is not None
    assert job.error["code"] == "unavailable"
    assert job.next_attempt_at == next_attempt_at
    assert job.locked_until is None
