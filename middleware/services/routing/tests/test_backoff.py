import pytest

from routing import backoff


def test_retry_delay_grows_exponentially_and_is_capped(monkeypatch):
    calls = []

    def uniform(low, high):
        calls.append((low, high))
        return high

    monkeypatch.setattr(backoff.random, "uniform", uniform)

    assert backoff.retry_delay(1, base_seconds=1.0, max_seconds=5.0) == 1.0
    assert backoff.retry_delay(2, base_seconds=1.0, max_seconds=5.0) == 2.0
    assert backoff.retry_delay(3, base_seconds=1.0, max_seconds=5.0) == 4.0
    assert backoff.retry_delay(4, base_seconds=1.0, max_seconds=5.0) == 5.0
    assert calls == [(0, 1.0), (0, 2.0), (0, 4.0), (0, 5.0)]


def test_total_backoff_sums_capped_exponential_delays():
    assert backoff.total_backoff_seconds(5, 1.0, 30.0) == 15.0
    assert backoff.total_backoff_seconds(5, 1.0, 5.0) == 12.0
    assert backoff.total_backoff_seconds(1, 1.0, 30.0) == 0.0


def test_retry_delay_is_zero_when_backoff_is_disabled(monkeypatch):
    monkeypatch.setattr(
        backoff.random,
        "uniform",
        lambda *_: pytest.fail("não deve sortear"),
    )

    assert backoff.retry_delay(3, base_seconds=0.0, max_seconds=5.0) == 0.0
