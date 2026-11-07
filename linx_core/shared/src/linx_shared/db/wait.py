from __future__ import annotations

import logging
import math
import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, NoSuchModuleError, SQLAlchemyError

from linx_shared.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseNotReadyError(RuntimeError):
    """Banco inacessível ou DATABASE_URL inválida durante a espera."""


def _validate_url(database_url: str) -> str:
    """Normaliza e valida a URL antes de qualquer tentativa de conexão.

    Uma string vazia é rejeitada mesmo que o ambiente tenha uma URL
    configurada, porque o chamador pediu explicitamente por aquela URL.
    """
    candidate = (database_url or "").strip()
    if not candidate:
        raise DatabaseNotReadyError(
            "DATABASE_URL is empty; set it in the environment before "
            "waiting for the database."
        )
    try:
        make_url(candidate).get_dialect()
    except (ArgumentError, NoSuchModuleError, ValueError) as exc:
        raise DatabaseNotReadyError(
            f"DATABASE_URL is not a valid SQLAlchemy URL: {exc}"
        ) from exc
    return candidate


def _try_connect(database_url: str, connect_timeout: int) -> None:
    """Faz uma única tentativa de conexão e executa ``SELECT 1``."""
    engine = create_engine(
        database_url,
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def wait_for_db(
    database_url: str | None = None,
    *,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 2.0,
    connect_timeout: int | None = None,
) -> None:
    """Aguarda o banco aceitar conexões, útil em initContainers.

    ``database_url=None`` usa ``settings.database_url``; qualquer outro
    valor é validado e usado como veio. Levanta ``DatabaseNotReadyError``
    quando a URL é inválida ou o timeout expira sem sucesso.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise DatabaseNotReadyError(
            "timeout_seconds must be a finite number greater than 0, got "
            f"{timeout_seconds!r}"
        )
    if not math.isfinite(interval_seconds) or interval_seconds < 0:
        raise DatabaseNotReadyError(
            "interval_seconds must be a finite number greater than or equal "
            f"to 0, got {interval_seconds!r}"
        )
    if connect_timeout is None:
        connect_timeout = settings.db_connect_timeout

    raw_url = settings.database_url if database_url is None else database_url
    url = _validate_url(raw_url)
    deadline = time.monotonic() + timeout_seconds
    last_error: SQLAlchemyError | None = None
    attempts = 0

    while True:
        attempts += 1
        try:
            _try_connect(url, connect_timeout)
            return
        except SQLAlchemyError as exc:
            last_error = exc
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DatabaseNotReadyError(
                    f"Database not ready after {timeout_seconds}s "
                    f"({attempts} attempts): {last_error}"
                ) from last_error
            logger.warning(
                "Database not ready (attempt %d): %s; retrying in %.2fs",
                attempts,
                exc,
                interval_seconds,
            )
            time.sleep(min(interval_seconds, remaining))


def _timeout_from_env(default: float = 300.0) -> float:
    """Lê ``WAIT_DB_TIMEOUT_SECONDS`` para o entrypoint ``python -m``.

    Mantém o default programático de ``wait_for_db`` em 60s; apenas o módulo
    executado via ``python -m linx_shared.db.wait`` assume 300s por padrão,
    tempo razoável para um cluster frio que faz ``pull``/``initdb`` do
    ``postgres:15-alpine``.
    """
    raw = os.environ.get("WAIT_DB_TIMEOUT_SECONDS")
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise DatabaseNotReadyError(
            "WAIT_DB_TIMEOUT_SECONDS must be a number of seconds, got "
            f"{raw!r}"
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise DatabaseNotReadyError(
            "WAIT_DB_TIMEOUT_SECONDS must be a finite number of seconds "
            f"greater than 0, got {raw!r}"
        )
    return value


if __name__ == "__main__":
    wait_for_db(timeout_seconds=_timeout_from_env())
