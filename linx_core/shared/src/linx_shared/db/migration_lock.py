import logging
import math
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

MIGRATION_LOCK_KEY = 927351


class MigrationLockTimeoutError(RuntimeError):
    """O advisory lock de migração não foi adquirido dentro do prazo."""


def acquire_migration_lock(
    connection,
    *,
    timeout_seconds: float = 300.0,
    poll_interval: float = 0.5,
) -> None:
    """Adquire o advisory lock de migração com deadline.

    Usa ``pg_try_advisory_lock`` (não bloqueante) em loop até adquirir ou até
    ``timeout_seconds`` expirar. Levanta ``MigrationLockTimeoutError`` no
    timeout para que um rollout nunca fique preso para sempre esperando o lock.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be a finite number greater than 0, got "
            f"{timeout_seconds!r}"
        )
    if not math.isfinite(poll_interval) or poll_interval < 0:
        raise ValueError(
            "poll_interval must be a finite number greater than or equal "
            f"to 0, got {poll_interval!r}"
        )

    deadline = time.monotonic() + timeout_seconds
    while True:
        result = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": MIGRATION_LOCK_KEY},
        )
        if result.scalar():
            connection.commit()
            return
        # Lock não adquirido: encerra a transação ociosa antes de retentar.
        connection.rollback()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MigrationLockTimeoutError(
                f"Timed out after {timeout_seconds}s waiting for migration "
                f"advisory lock {MIGRATION_LOCK_KEY}"
            )
        time.sleep(min(poll_interval, remaining))


def release_migration_lock(connection) -> None:
    """Libera o advisory lock sem mascarar o erro original da migração.

    Qualquer falha do SQLAlchemy é logada como warning e a transação é
    revertida; a função nunca levanta, para que uma falha aqui não esconda a
    exceção real de ``run_migrations``.
    """
    try:
        connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": MIGRATION_LOCK_KEY},
        )
        connection.commit()
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to release migration advisory lock %s: %s",
            MIGRATION_LOCK_KEY,
            exc,
        )
        try:
            connection.rollback()
        except SQLAlchemyError as rollback_exc:
            logger.warning(
                "Rollback after failed migration lock release also failed: %s",
                rollback_exc,
            )
