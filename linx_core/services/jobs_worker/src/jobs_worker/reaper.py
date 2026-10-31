import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from linx_shared.jobs.constants import (
    JOB_EVENTS_EXCHANGE,
    JobStatus,
)
from linx_shared.jobs.envelope import JobEnvelope, JobError, JobStatusEvent
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

EXPIRED_LEASE_CODE = "lease_expired"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _db_now(session: Session) -> datetime:
    return session.scalar(select(func.clock_timestamp())) or _utcnow()


class JobReaper:
    """Recupera jobs cujo lease expirou sem confirmação."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        interval_seconds: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds

    def run_once(self) -> int:
        session = self._session_factory()
        try:
            jobs = self._expired_jobs(session)
            now = _db_now(session)
            for job in jobs:
                self._recover(session, job, now)
            session.commit()
            return len(jobs)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def run_forever(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                recovered = self.run_once()
                if recovered:
                    logger.warning(
                        "reaped %s jobs with expired lease",
                        recovered,
                    )
            except Exception:
                logger.exception("job reaper iteration failed")
            stop_event.wait(self._interval_seconds)

    @staticmethod
    def _expired_jobs(session: Session) -> list[Job]:
        statement = (
            select(Job)
            .where(
                Job.locked_until.is_not(None),
                Job.locked_until < func.clock_timestamp(),
                Job.status.in_(
                    (JobStatus.PENDING.value, JobStatus.RUNNING.value)
                ),
            )
            .with_for_update(skip_locked=True)
        )
        return list(session.scalars(statement).all())

    def _recover(
        self,
        session: Session,
        job: Job,
        now: datetime,
    ) -> None:
        job.next_attempt_at = now
        job.locked_until = None

        event = JobStatusEvent(
            job_id=job.id,
            type=job.type,
            status=JobStatus.PENDING,
            attempt=job.attempts,
            error=JobError(
                code=EXPIRED_LEASE_CODE,
                message="job lease expired before completion",
                retryable=True,
            ),
            next_attempt_at=now,
        )
        session.add(
            JobOutbox(
                job_id=job.id,
                exchange=JOB_EVENTS_EXCHANGE,
                routing_key=f"{job.type}.retry",
                payload=event.model_dump(mode="json"),
            )
        )

        command = JobEnvelope(
            job_id=job.id,
            type=job.type,
            version=job.version,
            tenant_id=job.tenant_id,
            subject_id=job.subject_id,
            payload=job.payload,
            attempt=job.attempts,
            created_at=job.created_at,
        )
        session.add(
            JobOutbox(
                job_id=job.id,
                exchange=job.command_exchange,
                routing_key=job.command_routing_key,
                payload=command.model_dump(mode="json"),
                next_attempt_at=now,
            )
        )

        logger.info(
            "released expired job lease job_id=%s type=%s attempt=%s",
            job.id,
            job.type,
            job.attempts,
        )
