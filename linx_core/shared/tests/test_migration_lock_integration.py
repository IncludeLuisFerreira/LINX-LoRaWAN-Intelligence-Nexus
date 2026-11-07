import os
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from linx_shared.db.migration_lock import (
    MigrationLockTimeoutError,
    acquire_migration_lock,
    release_migration_lock,
)


def _resolve_database_url() -> str | None:
    """URL do Postgres para o teste de integração.

    Em CI (GitHub Actions define ``CI=true``) usa ``DATABASE_URL``, que o
    ``backend-ci.yml`` aponta para o serviço Postgres real. Localmente exige o
    opt-in explícito ``TEST_DATABASE_URL``, porque a conftest compartilhada
    injeta um ``DATABASE_URL`` default inacessível fora do CI.
    """
    if os.environ.get("CI"):
        return os.environ.get("DATABASE_URL")
    return os.environ.get("TEST_DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not _resolve_database_url(),
    reason="TEST_DATABASE_URL is not set (or DATABASE_URL when CI=true); "
    "set TEST_DATABASE_URL to a throwaway Postgres URL to run this "
    "integration test",
)


def _database_url() -> str:
    url = _resolve_database_url()
    if url is None:
        pytest.skip("no Postgres URL configured for the integration test")
    return url


def test_lock_blocks_concurrent_acquire_and_times_out():
    url = _database_url()
    engine_a = create_engine(url, poolclass=NullPool)
    engine_b = create_engine(url, poolclass=NullPool)

    conn_a = engine_a.connect()
    conn_c = None
    error = {}

    def blocked_acquire() -> None:
        conn_b = engine_b.connect()
        try:
            acquire_migration_lock(conn_b, timeout_seconds=0.5)
        except MigrationLockTimeoutError as exc:
            error["timeout"] = exc
        finally:
            conn_b.close()

    try:
        acquire_migration_lock(conn_a)

        thread = threading.Thread(target=blocked_acquire)
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive(), "background acquire should time out"
        assert isinstance(error.get("timeout"), MigrationLockTimeoutError)

        release_migration_lock(conn_a)

        conn_c = engine_a.connect()
        acquire_migration_lock(conn_c, timeout_seconds=2)
        release_migration_lock(conn_c)
    finally:
        release_migration_lock(conn_a)
        if conn_c is not None:
            release_migration_lock(conn_c)
            conn_c.close()
        conn_a.close()
        engine_a.dispose()
        engine_b.dispose()
