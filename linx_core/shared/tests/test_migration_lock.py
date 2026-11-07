from linx_shared.db.migration_lock import (
    MIGRATION_LOCK_KEY,
    acquire_migration_lock,
    release_migration_lock,
)


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.commits = 0

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))

    def commit(self):
        self.commits += 1


def test_acquire_uses_advisory_lock_and_commits():
    connection = FakeConnection()

    acquire_migration_lock(connection)

    assert "pg_advisory_lock" in connection.executed[0][0]
    assert connection.executed[0][1] == {"key": MIGRATION_LOCK_KEY}
    assert connection.commits == 1


def test_release_uses_advisory_unlock_and_commits():
    connection = FakeConnection()

    release_migration_lock(connection)

    assert "pg_advisory_unlock" in connection.executed[0][0]
    assert connection.executed[0][1] == {"key": MIGRATION_LOCK_KEY}
    assert connection.commits == 1
