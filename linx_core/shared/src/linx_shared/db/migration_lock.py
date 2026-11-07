from sqlalchemy import text

MIGRATION_LOCK_KEY = 927351


def acquire_migration_lock(connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_lock(:key)"),
        {"key": MIGRATION_LOCK_KEY},
    )
    connection.commit()


def release_migration_lock(connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_unlock(:key)"),
        {"key": MIGRATION_LOCK_KEY},
    )
    connection.commit()
