import logging
import threading
from collections.abc import Callable

from linx_shared.db.base import SessionLocal
from linx_shared.jobs.broker import JobPublisher
from linx_shared.jobs.handlers import HandlerRegistry
from linx_shared.jobs.outbox import (
    OUTBOX_MAX_ATTEMPTS,
    relay_pending_outbox,
)
from sqlalchemy.orm import Session

from jobs_worker.handlers.provision_application import (
    ProvisionApplicationHandler,
)

logger = logging.getLogger(__name__)


def _not_leader_or_not_ready(
    leader_event: threading.Event | None,
    ready_event: threading.Event | None,
) -> bool:
    """Loop singleton deve aguardar (sem liderança ou deps não prontas)."""
    if leader_event is not None and not leader_event.is_set():
        return True
    if ready_event is not None and not ready_event.is_set():
        return True
    return False


def run_outbox_relay(
    stop_event: threading.Event,
    session_factory: Callable[[], Session],
    publisher: JobPublisher,
    poll_interval: float = 1.0,
    max_attempts: int = OUTBOX_MAX_ATTEMPTS,
    *,
    leader_event: threading.Event | None = None,
    ready_event: threading.Event | None = None,
) -> None:
    while not stop_event.is_set():
        if _not_leader_or_not_ready(leader_event, ready_event):
            stop_event.wait(poll_interval)
            continue
        session = session_factory()
        try:
            relay_pending_outbox(
                session,
                publisher,
                max_attempts=max_attempts,
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("outbox relay iteration failed")
        finally:
            session.close()
        stop_event.wait(poll_interval)


def build_registry() -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register(
        ProvisionApplicationHandler(session_factory=SessionLocal)
    )
    return registry
