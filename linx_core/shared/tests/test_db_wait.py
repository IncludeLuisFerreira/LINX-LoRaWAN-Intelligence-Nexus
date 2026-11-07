import pytest
from sqlalchemy.exc import OperationalError

from linx_shared.db import wait


def test_wait_for_db_rejects_empty_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db("", timeout_seconds=1)


def test_wait_for_db_rejects_invalid_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db("not-a-sqlalchemy-url", timeout_seconds=1)


def test_wait_for_db_retries_until_timeout(monkeypatch):
    calls = []

    def always_fail(url: str, connect_timeout: int) -> None:
        calls.append((url, connect_timeout))
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(wait, "_try_connect", always_fail)

    with pytest.raises(wait.DatabaseNotReadyError, match="after 0.01s"):
        wait.wait_for_db(
            "postgresql+psycopg://u:p@db:5432/db",
            timeout_seconds=0.01,
            interval_seconds=0,
        )

    assert len(calls) >= 2


def test_wait_for_db_returns_on_first_success(monkeypatch):
    calls = []

    def succeed(url: str, connect_timeout: int) -> None:
        calls.append((url, connect_timeout))

    monkeypatch.setattr(wait, "_try_connect", succeed)

    wait.wait_for_db(
        "postgresql+psycopg://u:p@db:5432/db",
        timeout_seconds=1,
        interval_seconds=0,
    )

    assert calls == [("postgresql+psycopg://u:p@db:5432/db", 2)]
