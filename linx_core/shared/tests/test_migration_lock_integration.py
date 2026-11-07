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

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
DATABASE_URL = os.environ.get("DATABASE_URL")

# A conftest compartilhada injeta um ``DATABASE_URL`` default (inacessível fora
# do CI) para que a engine base seja construída durante a coleta. Usar esse
# valor como gatilho do teste faria a suíte completa tentar conectar num banco
# inexistente e falhar. ``TEST_DATABASE_URL`` é o opt-in explícito para um
# Postgres descartável.
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not set; set it to a throwaway Postgres URL "
    "to run this integration test",
)


def _database_url() -> str:
    url = TEST_DATABASE_URL or DATABASE_URL
    if url is None:
        pytest.skip("TEST_DATABASE_URL and DATABASE_URL are both unset")
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
