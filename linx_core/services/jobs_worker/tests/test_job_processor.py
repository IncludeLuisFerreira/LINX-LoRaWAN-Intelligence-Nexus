from datetime import datetime, timedelta, timezone

import pytest
from linx_shared.jobs.constants import (
    JOB_DLX,
    JOB_EVENTS_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_DEAD,
    PROVISIONING_REQUESTED,
    JobStatus,
)
from linx_shared.jobs.envelope import JobEnvelope
from linx_shared.jobs.handlers import (
    HandlerRegistry,
    PermanentJobError,
    TransientJobError,
)
from linx_shared.models.job_outbox import JobOutbox
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from jobs_worker.processor import JobProcessor

RETRY_DELAYS = (5, 30, 120)


class StubHandler:
    job_type = JOB_TYPE_PROVISION_APPLICATION

    def __init__(self, *, result=None, error=None) -> None:
        self.result = result or {}
        self.error = error
        self.calls = 0

    def handle(self, job):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _registry(handler=None) -> HandlerRegistry:
    registry = HandlerRegistry()
    if handler is not None:
        registry.register(handler)
    return registry


def _envelope(job, *, attempt=0) -> JobEnvelope:
    return JobEnvelope(
        job_id=job.id,
        type=job.type,
        tenant_id=job.tenant_id,
        subject_id=job.subject_id,
        payload=job.payload,
        attempt=attempt,
        created_at=job.created_at,
    )


def _processor(session_factory, registry) -> JobProcessor:
    return JobProcessor(
        session_factory,
        registry,
        lock_seconds=60,
        retry_delays=RETRY_DELAYS,
    )


def _outbox(db_session, job_id):
    db_session.expire_all()
    return db_session.scalars(
        select(JobOutbox).where(JobOutbox.job_id == job_id)
    ).all()


def _by_routing_key(rows):
    return {row.routing_key: row for row in rows}


def test_success_writes_started_and_succeeded_without_terminal_status(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    handler = StubHandler(result={"container_id": "container-1"})
    processor = _processor(session_factory, _registry(handler))

    processor.process(_envelope(job))

    rows = _outbox(db_session, job.id)
    by_key = _by_routing_key(rows)
    assert set(by_key) == {
        f"{JOB_TYPE_PROVISION_APPLICATION}.started",
        f"{JOB_TYPE_PROVISION_APPLICATION}.succeeded",
    }
    assert by_key[f"{JOB_TYPE_PROVISION_APPLICATION}.started"].exchange == (
        JOB_EVENTS_EXCHANGE
    )
    started = by_key[f"{JOB_TYPE_PROVISION_APPLICATION}.started"]
    succeeded = by_key[f"{JOB_TYPE_PROVISION_APPLICATION}.succeeded"]
    assert started.payload["status"] == JobStatus.RUNNING.value
    assert succeeded.payload["status"] == JobStatus.SUCCEEDED.value
    assert succeeded.payload["result"] == {"container_id": "container-1"}
    assert succeeded.payload["attempt"] == 1

    db_session.expire_all()
    assert job.status == JobStatus.PENDING.value
    assert job.locked_until is None
    assert job.attempts == 1
    assert handler.calls == 1


def test_transient_writes_retry_event_and_delayed_command(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    error = TransientJobError(
        "temporary",
        code="unavailable",
        grpc_code="UNAVAILABLE",
    )
    processor = _processor(
        session_factory,
        _registry(StubHandler(error=error)),
    )

    processor.process(_envelope(job))

    rows = _outbox(db_session, job.id)
    by_key = _by_routing_key(rows)
    retry_key = f"{JOB_TYPE_PROVISION_APPLICATION}.retry"
    assert retry_key in by_key
    assert PROVISIONING_REQUESTED in by_key
    retry_event = by_key[retry_key]
    command = by_key[PROVISIONING_REQUESTED]
    assert retry_event.exchange == JOB_EVENTS_EXCHANGE
    assert retry_event.payload["status"] == JobStatus.PENDING.value
    assert retry_event.payload["error"]["code"] == "unavailable"
    assert retry_event.payload["error"]["retryable"] is True
    assert retry_event.payload["error"]["grpc_code"] == "UNAVAILABLE"
    assert command.exchange == job.command_exchange

    db_session.expire_all()
    assert job.next_attempt_at is not None
    assert command.next_attempt_at == job.next_attempt_at
    assert command.next_attempt_at > datetime.now(timezone.utc)
    assert command.next_attempt_at <= datetime.now(timezone.utc) + (
        timedelta(seconds=RETRY_DELAYS[0])
    )
    assert job.locked_until is None
    assert job.status == JobStatus.PENDING.value


def test_permanent_writes_failed_event_and_dlq(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    error = PermanentJobError(
        "invalid",
        code="invalid_argument",
        grpc_code="FAILED_PRECONDITION",
    )
    processor = _processor(
        session_factory,
        _registry(StubHandler(error=error)),
    )

    processor.process(_envelope(job))

    rows = _outbox(db_session, job.id)
    by_key = _by_routing_key(rows)
    failed_key = f"{JOB_TYPE_PROVISION_APPLICATION}.failed"
    assert failed_key in by_key
    failed = by_key[failed_key]
    dead = by_key[PROVISIONING_DEAD]
    assert failed.exchange == JOB_EVENTS_EXCHANGE
    assert failed.payload["status"] == JobStatus.FAILED.value
    assert failed.payload["error"]["code"] == "invalid_argument"
    assert failed.payload["error"]["retryable"] is False
    assert dead.exchange == JOB_DLX
    assert dead.routing_key == PROVISIONING_DEAD

    db_session.expire_all()
    assert job.locked_until is None
    assert job.status == JobStatus.PENDING.value


def test_max_attempts_writes_failed_event_and_dlq(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(max_attempts=1)
    processor = _processor(
        session_factory,
        _registry(StubHandler(error=TransientJobError("temporary"))),
    )

    processor.process(_envelope(job))

    rows = _outbox(db_session, job.id)
    by_key = _by_routing_key(rows)
    retry_key = f"{JOB_TYPE_PROVISION_APPLICATION}.retry"
    failed_key = f"{JOB_TYPE_PROVISION_APPLICATION}.failed"
    assert failed_key in by_key
    assert retry_key not in by_key
    assert PROVISIONING_REQUESTED not in by_key
    assert by_key[PROVISIONING_DEAD].exchange == JOB_DLX
    assert by_key[failed_key].payload["attempt"] == 1


def test_duplicate_message_with_valid_lease_is_ignored(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(
        locked_until=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    handler = StubHandler(result={"container_id": "container-1"})
    processor = _processor(session_factory, _registry(handler))

    processor.process(_envelope(job))

    assert _outbox(db_session, job.id) == []
    assert handler.calls == 0


def test_unexpected_exception_becomes_handler_error_retry(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory()
    processor = _processor(
        session_factory,
        _registry(StubHandler(error=ValueError("boom"))),
    )

    processor.process(_envelope(job))

    rows = _outbox(db_session, job.id)
    by_key = _by_routing_key(rows)
    retry_key = f"{JOB_TYPE_PROVISION_APPLICATION}.retry"
    assert by_key[retry_key].payload["error"]["code"] == "handler_error"
    assert by_key[retry_key].payload["error"]["retryable"] is True
    assert PROVISIONING_REQUESTED in by_key


def test_unknown_type_becomes_permanent_failure(
    session_factory,
    db_session,
    job_factory,
):
    job = job_factory(job_type="unknown.job")
    processor = _processor(session_factory, _registry())

    processor.process(_envelope(job))

    rows = _outbox(db_session, job.id)
    by_key = _by_routing_key(rows)
    failed_key = "unknown.job.failed"
    assert failed_key in by_key
    assert by_key[failed_key].payload["status"] == JobStatus.FAILED.value
    assert by_key[failed_key].payload["error"]["retryable"] is False
    assert by_key[PROVISIONING_DEAD].exchange == JOB_DLX


def test_commit_failure_leaves_no_uncommitted_outbox_row(
    connection,
    db_session,
    job_factory,
):
    job = job_factory()
    handler = StubHandler(result={"container_id": "container-1"})
    registry = _registry(handler)

    class FailingCommitSession(Session):
        def commit(self) -> None:
            raise RuntimeError("commit failed")

    failing_factory = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        class_=FailingCommitSession,
    )
    processor = _processor(failing_factory, registry)

    with pytest.raises(RuntimeError, match="commit failed"):
        processor.process(_envelope(job))

    assert _outbox(db_session, job.id) == []
    assert handler.calls == 0
