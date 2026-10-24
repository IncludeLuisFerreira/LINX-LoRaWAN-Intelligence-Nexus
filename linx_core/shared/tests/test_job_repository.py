from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from linx_shared.jobs.constants import (
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_REQUESTED,
    JobStatus,
)
from linx_shared.jobs.envelope import JobError, JobStatusEvent
from linx_shared.jobs.repository import (
    apply_status_event,
    claim_job,
    create_job_with_outbox,
    get_active_job,
    get_job,
    release_job,
)
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox
from linx_shared.models.tenant import Tenant


def _create_tenant(session: Session, name: str | None = None) -> Tenant:
    tenant = Tenant(name=name or f"tenant-{uuid4()}")
    session.add(tenant)
    session.flush()
    return tenant


def _create_job(
    session: Session,
    *,
    tenant_id: UUID,
    deduplication_key: str | None = None,
    subject_id: UUID | None = None,
) -> Job:
    return create_job_with_outbox(
        session,
        job_type=JOB_TYPE_PROVISION_APPLICATION,
        tenant_id=tenant_id,
        subject_id=subject_id or uuid4(),
        payload={"application_id": str(uuid4())},
        deduplication_key=deduplication_key or f"job-{uuid4()}",
        exchange=JOB_EXCHANGE,
        routing_key=PROVISIONING_REQUESTED,
    )


def _event(
    job: Job,
    status: JobStatus,
    *,
    attempt: int | None = None,
    result: dict | None = None,
    error: JobError | None = None,
    finished_at: datetime | None = None,
    next_attempt_at: datetime | None = None,
) -> JobStatusEvent:
    return JobStatusEvent(
        job_id=job.id,
        type=job.type,
        status=status,
        attempt=job.attempts if attempt is None else attempt,
        result=result,
        error=error,
        finished_at=finished_at,
        next_attempt_at=next_attempt_at,
    )


def test_create_job_with_outbox_creates_both_rows(db_session):
    tenant = _create_tenant(db_session)
    subject_id = uuid4()
    deduplication_key = f"provisioning.application:{subject_id}"

    job = create_job_with_outbox(
        db_session,
        job_type=JOB_TYPE_PROVISION_APPLICATION,
        tenant_id=tenant.id,
        subject_id=subject_id,
        payload={"application_id": str(subject_id)},
        deduplication_key=deduplication_key,
        exchange=JOB_EXCHANGE,
        routing_key=PROVISIONING_REQUESTED,
        trace_id=uuid4(),
    )

    outbox = db_session.scalars(
        select(JobOutbox).where(JobOutbox.job_id == job.id)
    ).one()

    assert job.status == JobStatus.PENDING.value
    assert job.attempts == 0
    assert job.command_exchange == JOB_EXCHANGE
    assert job.command_routing_key == PROVISIONING_REQUESTED
    assert outbox.exchange == JOB_EXCHANGE
    assert outbox.routing_key == PROVISIONING_REQUESTED
    assert outbox.published_at is None
    assert outbox.attempts == 0
    assert outbox.payload["job_id"] == str(job.id)
    assert outbox.payload["type"] == JOB_TYPE_PROVISION_APPLICATION
    assert outbox.payload["tenant_id"] == str(tenant.id)
    assert outbox.payload["subject_id"] == str(subject_id)
    assert outbox.payload["attempt"] == 0
    assert outbox.payload["trace_id"] is not None


def test_get_active_job_ignores_terminal_jobs(db_session):
    tenant = _create_tenant(db_session)
    active = _create_job(
        db_session,
        tenant_id=tenant.id,
        deduplication_key="active",
    )
    terminal = _create_job(
        db_session,
        tenant_id=tenant.id,
        deduplication_key="terminal",
    )
    terminal.status = JobStatus.SUCCEEDED.value
    db_session.flush()

    assert get_active_job(db_session, "active") is active
    assert get_active_job(db_session, "terminal") is None


def test_create_job_with_outbox_respects_active_dedup_index(db_session):
    tenant = _create_tenant(db_session)
    _create_job(
        db_session,
        tenant_id=tenant.id,
        deduplication_key="duplicated",
    )

    with pytest.raises(IntegrityError):
        _create_job(
            db_session,
            tenant_id=tenant.id,
            deduplication_key="duplicated",
        )


def test_claim_job_sets_lease_and_attempt(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    before = datetime.now(timezone.utc)

    claimed = claim_job(db_session, job.id, lock_seconds=60)

    assert claimed is job
    assert job.attempts == 1
    assert job.status == JobStatus.PENDING.value
    assert job.started_at is not None
    assert job.locked_until is not None
    assert job.locked_until > before + timedelta(seconds=50)


def test_claim_job_ignores_valid_lease(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    first_started_at = job.started_at

    assert claim_job(db_session, job.id, lock_seconds=60) is None
    assert job.attempts == 1
    assert job.started_at == first_started_at


def test_claim_job_ignores_future_next_attempt(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=60)
    db_session.flush()

    assert claim_job(db_session, job.id, lock_seconds=60) is None
    assert job.attempts == 0
    assert job.locked_until is None


def test_claim_job_reclaims_expired_lease(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    first_started_at = job.started_at
    job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()

    claimed = claim_job(db_session, job.id, lock_seconds=60)

    assert claimed is job
    assert job.attempts == 2
    assert job.started_at == first_started_at
    assert job.locked_until > datetime.now(timezone.utc)
    assert job.status == JobStatus.PENDING.value


@pytest.mark.parametrize(
    "status",
    [JobStatus.SUCCEEDED, JobStatus.FAILED],
)
def test_claim_job_refuses_terminal_jobs(db_session, status):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    job.status = status.value
    db_session.flush()

    assert claim_job(db_session, job.id, lock_seconds=60) is None
    assert job.attempts == 0
    assert job.locked_until is None


def test_release_job_clears_lease(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=30)

    released = release_job(db_session, job.id, next_attempt_at=next_attempt_at)

    assert released is job
    assert job.locked_until is None
    assert job.next_attempt_at == next_attempt_at
    assert job.status == JobStatus.PENDING.value
    assert job.attempts == 1


def test_release_job_keeps_next_attempt_when_not_provided(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    job.next_attempt_at = next_attempt_at
    db_session.flush()

    released = release_job(db_session, job.id)

    assert released is job
    assert job.locked_until is None
    assert job.next_attempt_at == next_attempt_at
    assert job.status == JobStatus.PENDING.value
    assert job.attempts == 1


def test_apply_status_event_is_idempotent(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)

    started = _event(job, JobStatus.RUNNING)
    apply_status_event(db_session, started)

    assert job.status == JobStatus.RUNNING.value
    assert job.started_at is not None

    finished_at = datetime.now(timezone.utc)
    succeeded = _event(
        job,
        JobStatus.SUCCEEDED,
        result={"port": 8200},
        finished_at=finished_at,
    )
    apply_status_event(db_session, succeeded)

    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"port": 8200}
    assert job.finished_at == finished_at
    assert job.locked_until is None

    apply_status_event(db_session, succeeded)

    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"port": 8200}
    assert job.finished_at == finished_at
    assert job.locked_until is None


def test_apply_status_event_ignores_stale_attempt(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    job.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()
    claim_job(db_session, job.id, lock_seconds=60)

    stale = _event(
        job,
        JobStatus.SUCCEEDED,
        attempt=1,
        result={"port": 8200},
        finished_at=datetime.now(timezone.utc),
    )
    apply_status_event(db_session, stale)

    assert job.attempts == 2
    assert job.status == JobStatus.PENDING.value
    assert job.result is None
    assert job.finished_at is None


def test_apply_status_event_ignores_running_with_future_next_attempt(
    db_session,
):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=60)
    release_job(db_session, job.id, next_attempt_at=next_attempt_at)

    apply_status_event(db_session, _event(job, JobStatus.RUNNING))

    assert job.status == JobStatus.PENDING.value
    assert job.next_attempt_at == next_attempt_at
    assert job.locked_until is None


def test_apply_status_event_ignores_running_after_succeeded(db_session):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    finished_at = datetime.now(timezone.utc)
    apply_status_event(
        db_session,
        _event(
            job,
            JobStatus.SUCCEEDED,
            result={"port": 8200},
            finished_at=finished_at,
        ),
    )

    apply_status_event(db_session, _event(job, JobStatus.RUNNING))

    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"port": 8200}
    assert job.finished_at == finished_at


@pytest.mark.parametrize(
    "first, second",
    [
        (JobStatus.SUCCEEDED, JobStatus.FAILED),
        (JobStatus.FAILED, JobStatus.SUCCEEDED),
    ],
)
def test_apply_status_event_does_not_overwrite_terminal_state(
    db_session,
    first,
    second,
):
    tenant = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)
    claim_job(db_session, job.id, lock_seconds=60)
    first_result = {"port": 8200} if first is JobStatus.SUCCEEDED else None
    first_error = (
        None
        if first is JobStatus.SUCCEEDED
        else JobError(
            code="permanent_error",
            message="failed",
            retryable=False,
        )
    )
    finished_at = datetime.now(timezone.utc)
    apply_status_event(
        db_session,
        _event(
            job,
            first,
            result=first_result,
            error=first_error,
            finished_at=finished_at,
        ),
    )

    second_result = {"port": 9999} if second is JobStatus.SUCCEEDED else None
    second_error = (
        None
        if second is JobStatus.SUCCEEDED
        else JobError(
            code="permanent_error",
            message="late failure",
            retryable=False,
        )
    )
    apply_status_event(
        db_session,
        _event(
            job,
            second,
            result=second_result,
            error=second_error,
            finished_at=datetime.now(timezone.utc),
        ),
    )

    assert job.status == first.value
    assert job.result == first_result
    assert job.error == (
        first_error.model_dump(mode="json") if first_error else None
    )
    assert job.finished_at == finished_at


def test_get_job_is_tenant_scoped(db_session):
    tenant = _create_tenant(db_session)
    other = _create_tenant(db_session)
    job = _create_job(db_session, tenant_id=tenant.id)

    assert get_job(db_session, tenant.id, job.id) is job
    assert get_job(db_session, other.id, job.id) is None
