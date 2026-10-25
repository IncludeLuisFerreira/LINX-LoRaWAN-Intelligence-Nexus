import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from linx_shared.jobs.constants import (
    JOB_DLX,
    JOB_EVENTS_EXCHANGE,
    PROVISIONING_DEAD,
    JobStatus,
)
from linx_shared.jobs.envelope import JobEnvelope, JobError, JobStatusEvent
from linx_shared.jobs.handlers import (
    HandlerRegistry,
    PermanentJobError,
    TransientJobError,
)
from linx_shared.jobs.repository import claim_job
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobProcessor:
    """Executa handlers e grava eventos/comandos no outbox.

    O processador nunca publica no RabbitMQ nem escreve o status terminal do
    job: o ``StatusProcessor`` aplica os eventos resultantes.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        registry: HandlerRegistry,
        *,
        lock_seconds: int,
        retry_delays: tuple[int, ...],
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._lock_seconds = lock_seconds
        self._retry_delays = retry_delays

    def process(self, envelope: JobEnvelope) -> None:
        started = time.perf_counter()
        outcome = "skipped"
        attempt = envelope.attempt
        session = self._session_factory()
        try:
            job = claim_job(
                session,
                envelope.job_id,
                lock_seconds=self._lock_seconds,
            )
            if job is None:
                session.rollback()
                return

            attempt = job.attempts
            if job.attempts > job.max_attempts:
                self._add_failed(
                    session,
                    job,
                    envelope,
                    PermanentJobError(
                        "job exceeded max attempts after lease recovery",
                        code="attempts_exhausted",
                    ),
                )
                session.commit()
                outcome = JobStatus.FAILED.value
                return

            self._add_started(session, job, envelope)
            session.commit()

            try:
                handler = self._registry.get(job.type)
            except KeyError:
                self._add_failed(
                    session,
                    job,
                    envelope,
                    PermanentJobError(
                        f"unknown job type: {job.type}",
                        code="unknown_job_type",
                    ),
                )
                session.commit()
                outcome = JobStatus.FAILED.value
                return

            try:
                result = handler.handle(job)
            except PermanentJobError as exc:
                self._add_failed(session, job, envelope, exc)
                outcome = JobStatus.FAILED.value
            except TransientJobError as exc:
                outcome = self._add_transient(
                    session,
                    job,
                    envelope,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001
                outcome = self._add_transient(
                    session,
                    job,
                    envelope,
                    TransientJobError(
                        str(exc) or exc.__class__.__name__,
                        code="handler_error",
                    ),
                )
            else:
                self._add_succeeded(session, job, envelope, result)
                outcome = JobStatus.SUCCEEDED.value

            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "job message processed job_id=%s type=%s attempt=%s "
                "duration_ms=%.1f status=%s",
                envelope.job_id,
                envelope.type,
                attempt,
                duration_ms,
                outcome,
            )

    def _event(
        self,
        session: Session,
        job: Job,
        status: JobStatus,
        *,
        suffix: str,
        result: dict[str, Any] | None = None,
        error: JobError | None = None,
        next_attempt_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> JobOutbox:
        event = JobStatusEvent(
            job_id=job.id,
            type=job.type,
            status=status,
            attempt=job.attempts,
            result=result,
            error=error,
            next_attempt_at=next_attempt_at,
            finished_at=finished_at,
        )
        outbox = JobOutbox(
            job_id=job.id,
            exchange=JOB_EVENTS_EXCHANGE,
            routing_key=f"{job.type}.{suffix}",
            payload=event.model_dump(mode="json"),
        )
        session.add(outbox)
        return outbox

    def _command(
        self,
        session: Session,
        job: Job,
        envelope: JobEnvelope,
        *,
        exchange: str,
        routing_key: str,
        next_attempt_at: datetime | None = None,
    ) -> JobOutbox:
        command = JobEnvelope(
            job_id=job.id,
            type=job.type,
            version=job.version,
            tenant_id=job.tenant_id,
            subject_id=job.subject_id,
            payload=job.payload,
            attempt=job.attempts,
            created_at=job.created_at,
            trace_id=envelope.trace_id,
        )
        outbox = JobOutbox(
            job_id=job.id,
            exchange=exchange,
            routing_key=routing_key,
            payload=command.model_dump(mode="json"),
            next_attempt_at=next_attempt_at or _utcnow(),
        )
        session.add(outbox)
        return outbox

    def _add_started(
        self,
        session: Session,
        job: Job,
        envelope: JobEnvelope,
    ) -> None:
        self._event(session, job, JobStatus.RUNNING, suffix="started")

    def _add_succeeded(
        self,
        session: Session,
        job: Job,
        envelope: JobEnvelope,
        result: dict[str, Any],
    ) -> None:
        finished_at = _utcnow()
        job.locked_until = None
        job.next_attempt_at = None
        self._event(
            session,
            job,
            JobStatus.SUCCEEDED,
            suffix="succeeded",
            result=result,
            finished_at=finished_at,
        )

    def _add_transient(
        self,
        session: Session,
        job: Job,
        envelope: JobEnvelope,
        error: TransientJobError,
    ) -> str:
        if job.attempts >= job.max_attempts:
            self._add_failed(session, job, envelope, error)
            return JobStatus.FAILED.value

        index = min(job.attempts - 1, len(self._retry_delays) - 1)
        delay = self._retry_delays[index] if self._retry_delays else 0
        next_attempt_at = _utcnow() + timedelta(seconds=delay)

        job.next_attempt_at = next_attempt_at
        job.locked_until = None
        self._event(
            session,
            job,
            JobStatus.PENDING,
            suffix="retry",
            error=JobError(
                code=error.code,
                message=error.message,
                retryable=True,
                grpc_code=error.grpc_code,
            ),
            next_attempt_at=next_attempt_at,
        )
        self._command(
            session,
            job,
            envelope,
            exchange=job.command_exchange,
            routing_key=job.command_routing_key,
            next_attempt_at=next_attempt_at,
        )
        return JobStatus.PENDING.value

    def _add_failed(
        self,
        session: Session,
        job: Job,
        envelope: JobEnvelope,
        error: PermanentJobError | TransientJobError,
    ) -> None:
        job.locked_until = None
        self._event(
            session,
            job,
            JobStatus.FAILED,
            suffix="failed",
            error=JobError(
                code=error.code,
                message=error.message,
                retryable=False,
                grpc_code=error.grpc_code,
            ),
            finished_at=_utcnow(),
        )
        self._command(
            session,
            job,
            envelope,
            exchange=JOB_DLX,
            routing_key=PROVISIONING_DEAD,
        )
