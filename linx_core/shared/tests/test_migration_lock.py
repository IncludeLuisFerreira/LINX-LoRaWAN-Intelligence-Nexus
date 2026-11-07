import logging
import math

import pytest
from sqlalchemy.exc import OperationalError

from linx_shared.db.migration_lock import (
    MIGRATION_LOCK_KEY,
    MigrationLockTimeoutError,
    acquire_migration_lock,
    release_migration_lock,
)


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class FakeConnection:
    def __init__(self, results=None, *, default=True):
        self._results = list(results) if results is not None else []
        self._default = default
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self._raise_on_execute = None

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        if self._raise_on_execute is not None:
            raise self._raise_on_execute
        value = self._results.pop(0) if self._results else self._default
        return FakeResult(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_acquire_uses_try_advisory_lock_and_commits_on_success():
    connection = FakeConnection()

    acquire_migration_lock(connection)

    assert "pg_try_advisory_lock" in connection.executed[0][0]
    assert connection.executed[0][1] == {"key": MIGRATION_LOCK_KEY}
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_acquire_retries_after_false_then_succeeds():
    connection = FakeConnection(results=[False, True])

    acquire_migration_lock(connection, poll_interval=0)

    assert len(connection.executed) == 2
    assert connection.commits == 1
    assert connection.rollbacks == 1


def test_acquire_raises_timeout_when_lock_never_free():
    connection = FakeConnection(default=False)

    with pytest.raises(MigrationLockTimeoutError, match="927351"):
        acquire_migration_lock(
            connection, timeout_seconds=0.01, poll_interval=0
        )

    assert connection.commits == 0
    assert connection.rollbacks >= 1


@pytest.mark.parametrize("timeout_seconds", [math.nan, math.inf, 0, -1])
def test_acquire_rejects_invalid_timeout(timeout_seconds):
    connection = FakeConnection()

    with pytest.raises(ValueError, match="timeout_seconds"):
        acquire_migration_lock(connection, timeout_seconds=timeout_seconds)


@pytest.mark.parametrize("poll_interval", [math.nan, math.inf, -1])
def test_acquire_rejects_invalid_poll_interval(poll_interval):
    connection = FakeConnection()

    with pytest.raises(ValueError, match="poll_interval"):
        acquire_migration_lock(connection, poll_interval=poll_interval)


def test_release_uses_advisory_unlock_and_commits():
    connection = FakeConnection()

    release_migration_lock(connection)

    assert "pg_advisory_unlock" in connection.executed[0][0]
    assert connection.executed[0][1] == {"key": MIGRATION_LOCK_KEY}
    assert connection.commits == 1


def test_release_swallows_error_and_rolls_back(caplog):
    connection = FakeConnection()
    connection._raise_on_execute = OperationalError(
        "SELECT pg_advisory_unlock(:key)", {}, Exception("boom")
    )

    with caplog.at_level(logging.WARNING):
        release_migration_lock(connection)  # não pode levantar

    assert connection.rollbacks == 1
    assert "Failed to release migration advisory lock" in caplog.text
