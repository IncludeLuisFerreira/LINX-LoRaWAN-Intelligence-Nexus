from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from linx_shared.jobs.constants import JobStatus
from linx_shared.jobs.envelope import JobEnvelope, JobStatusEvent
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox

_TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED.value, JobStatus.FAILED.value}
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _lock_job(session: Session, job_id: UUID) -> Job | None:
    statement = select(Job).where(Job.id == job_id).with_for_update()
    return session.scalars(statement).one_or_none()


def get_active_job(session: Session, deduplication_key: str) -> Job | None:
    statement = select(Job).where(
        Job.deduplication_key == deduplication_key,
        Job.status.in_((JobStatus.PENDING.value, JobStatus.RUNNING.value)),
    )
    return session.scalars(statement).first()


def get_job(
    session: Session,
    tenant_id: UUID,
    job_id: UUID,
) -> Job | None:
    statement = select(Job).where(
        Job.id == job_id,
        Job.tenant_id == tenant_id,
    )
    return session.scalars(statement).one_or_none()


def _envelope_payload(job: Job, trace_id: UUID | None) -> dict[str, Any]:
    envelope = JobEnvelope(
        job_id=job.id,
        type=job.type,
        version=job.version,
        tenant_id=job.tenant_id,
        subject_id=job.subject_id,
        payload=job.payload,
        attempt=job.attempts,
        created_at=job.created_at,
        trace_id=trace_id,
    )
    return envelope.model_dump(mode="json")


def create_job_with_outbox(
    session: Session,
    *,
    job_type: str,
    tenant_id: UUID,
    subject_id: UUID,
    payload: dict[str, Any],
    deduplication_key: str,
    exchange: str,
    routing_key: str,
    max_attempts: int = 3,
    trace_id: UUID | None = None,
) -> Job:
    job = Job(
        type=job_type,
        tenant_id=tenant_id,
        subject_id=subject_id,
        payload=payload,
        command_exchange=exchange,
        command_routing_key=routing_key,
        deduplication_key=deduplication_key,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.flush()
    session.add(
        JobOutbox(
            job_id=job.id,
            exchange=exchange,
            routing_key=routing_key,
            payload=_envelope_payload(job, trace_id),
        )
    )
    return job


def claim_job(
    session: Session,
    job_id: UUID,
    *,
    lock_seconds: int,
) -> Job | None:
    now = _utcnow()
    job = _lock_job(session, job_id)
    if job is None:
        return None
    if job.status in _TERMINAL_STATUSES:
        return None
    if job.locked_until is not None and job.locked_until > now:
        return None
    if job.next_attempt_at is not None and job.next_attempt_at > now:
        return None

    job.attempts += 1
    if job.started_at is None:
        job.started_at = now
    job.locked_until = now + timedelta(seconds=lock_seconds)
    return job


def release_job(
    session: Session,
    job_id: UUID,
    *,
    next_attempt_at: datetime | None = None,
) -> Job | None:
    job = _lock_job(session, job_id)
    if job is None:
        return None

    job.locked_until = None
    if next_attempt_at is not None:
        job.next_attempt_at = next_attempt_at
    return job


def apply_status_event(
    session: Session,
    event: JobStatusEvent,
) -> Job | None:
    job = _lock_job(session, event.job_id)
    if job is None:
        return None
    if event.attempt != job.attempts:
        return job
    if job.status in _TERMINAL_STATUSES and event.status.value != job.status:
        return job

    now = _utcnow()
    if event.status == JobStatus.RUNNING:
        if job.next_attempt_at is not None and job.next_attempt_at > now:
            return job
        job.status = JobStatus.RUNNING.value
        if job.started_at is None:
            job.started_at = now
        job.next_attempt_at = None
        return job

    if event.status == JobStatus.PENDING:
        job.status = JobStatus.PENDING.value
        job.next_attempt_at = event.next_attempt_at
        job.locked_until = None
        if event.error is not None:
            job.error = event.error.model_dump(mode="json")
        return job

    job.status = event.status.value
    job.result = event.result
    if event.error is not None:
        job.error = event.error.model_dump(mode="json")
    else:
        job.error = None
    job.finished_at = event.finished_at or job.finished_at or now
    job.next_attempt_at = event.next_attempt_at
    job.locked_until = None
    return job
