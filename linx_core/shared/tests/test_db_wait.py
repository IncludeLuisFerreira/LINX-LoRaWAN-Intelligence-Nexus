import math

import pytest
from sqlalchemy.exc import OperationalError

from linx_shared.db import wait


def test_wait_for_db_rejects_empty_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db("", timeout_seconds=1)


def test_wait_for_db_rejects_invalid_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db("not-a-sqlalchemy-url", timeout_seconds=1)


def test_wait_for_db_rejects_invalid_port_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db(
            "postgresql+psycopg://u:p@db:notaport/db", timeout_seconds=1
        )


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


def test_wait_for_db_uses_settings_connect_timeout(monkeypatch):
    calls = []

    def succeed(url: str, connect_timeout: int) -> None:
        calls.append((url, connect_timeout))

    monkeypatch.setattr(wait, "_try_connect", succeed)
    monkeypatch.setattr(wait.settings, "db_connect_timeout", 7)

    wait.wait_for_db(
        "postgresql+psycopg://u:p@db:5432/db",
        timeout_seconds=1,
        interval_seconds=0,
    )

    assert calls == [("postgresql+psycopg://u:p@db:5432/db", 7)]


@pytest.mark.parametrize("timeout_seconds", [math.nan, math.inf, 0, -1])
def test_wait_for_db_rejects_invalid_timeout(timeout_seconds):
    with pytest.raises(wait.DatabaseNotReadyError, match="timeout_seconds"):
        wait.wait_for_db(timeout_seconds=timeout_seconds)


def test_timeout_from_env_default(monkeypatch):
    monkeypatch.delenv("WAIT_DB_TIMEOUT_SECONDS", raising=False)
    assert wait._timeout_from_env() == 300.0


def test_timeout_from_env_override(monkeypatch):
    monkeypatch.setenv("WAIT_DB_TIMEOUT_SECONDS", "180")
    assert wait._timeout_from_env() == 180.0


def test_timeout_from_env_invalid(monkeypatch):
    monkeypatch.setenv("WAIT_DB_TIMEOUT_SECONDS", "abc")
    with pytest.raises(
        wait.DatabaseNotReadyError, match="WAIT_DB_TIMEOUT_SECONDS"
    ):
        wait._timeout_from_env()


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "-1", "0", "abc"])
def test_timeout_from_env_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("WAIT_DB_TIMEOUT_SECONDS", raw)
    with pytest.raises(
        wait.DatabaseNotReadyError, match="WAIT_DB_TIMEOUT_SECONDS"
    ):
        wait._timeout_from_env()
