import threading

from jobs_worker import main


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, *args: object, **kwargs: object) -> None:
        return None


class FakeEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()


def test_background_waiter_sets_ready_after_checks(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(main, "check", lambda: calls.append("check"))
    monkeypatch.setattr(main, "engine", FakeEngine())
    monkeypatch.setattr(
        main,
        "_declare_topology",
        lambda url, queue: calls.append(("declare", url, queue)),
    )

    ready = threading.Event()
    stop = threading.Event()
    main._wait_for_dependencies_background(
        stop, ready, "amqp://broker", "linx.jobs"
    )

    assert ready.is_set()
    assert calls == ["check", ("declare", "amqp://broker", "linx.jobs")]


def test_background_waiter_retries_until_ready(monkeypatch):
    attempts = {"count": 0}

    def flaky_check() -> None:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("db indisponível")

    monkeypatch.setattr(main, "check", flaky_check)
    monkeypatch.setattr(main, "engine", FakeEngine())
    monkeypatch.setattr(main, "_declare_topology", lambda url, queue: None)
    monkeypatch.setattr(main, "READY_DELAY_SECONDS", 0.01)

    ready = threading.Event()
    stop = threading.Event()
    main._wait_for_dependencies_background(stop, ready, "amqp://broker", "q")

    assert ready.is_set()
    assert attempts["count"] == 2
