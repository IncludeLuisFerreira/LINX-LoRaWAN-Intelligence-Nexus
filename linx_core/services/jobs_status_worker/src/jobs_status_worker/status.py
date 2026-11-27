import logging
import time
from collections.abc import Callable

from linx_shared.jobs.envelope import JobStatusEvent
from linx_shared.jobs.repository import apply_status_event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class StatusProcessor:
    """Aplica eventos de status na tabela ``jobs``."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def process(self, event: JobStatusEvent) -> None:
        started = time.perf_counter()
        session = self._session_factory()
        try:
            apply_status_event(session, event)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "status event processed job_id=%s type=%s attempt=%s "
                "duration_ms=%.1f status=%s",
                event.job_id,
                event.type,
                event.attempt,
                duration_ms,
                event.status.value,
            )
