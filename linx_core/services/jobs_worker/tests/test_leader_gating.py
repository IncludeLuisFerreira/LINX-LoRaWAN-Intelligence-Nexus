import threading
import time

from jobs_worker import runtime
from jobs_worker.reaper import JobReaper


class FakeSession:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


class FakePublisher:
    pass


def _settle(predicate, timeout: float = 1.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _start_outbox(monkeypatch, leader_event, ready_event):
    calls: list[int] = []
    monkeypatch.setattr(
        runtime, "relay_pending_outbox", lambda *a, **k: calls.append(1)
    )
    stop = threading.Event()
    thread = threading.Thread(
        target=runtime.run_outbox_relay,
        args=(stop, lambda: FakeSession(), FakePublisher(), 0.01, 10),
        kwargs={"leader_event": leader_event, "ready_event": ready_event},
        daemon=True,
    )
    thread.start()
    return calls, stop, thread


def test_outbox_relay_idles_when_not_leader(monkeypatch):
    leader = threading.Event()
    ready = threading.Event()
    ready.set()
    calls, stop, thread = _start_outbox(monkeypatch, leader, ready)
    try:
        time.sleep(0.05)
        assert calls == []
    finally:
        stop.set()
        thread.join(timeout=1.0)


def test_outbox_relay_runs_when_leader(monkeypatch):
    leader = threading.Event()
    leader.set()
    ready = threading.Event()
    ready.set()
    calls, stop, thread = _start_outbox(monkeypatch, leader, ready)
    try:
        assert _settle(lambda: len(calls) > 0)
    finally:
        stop.set()
        thread.join(timeout=1.0)


def test_outbox_relay_stops_when_leadership_lost(monkeypatch):
    leader = threading.Event()
    leader.set()
    ready = threading.Event()
    ready.set()
    calls, stop, thread = _start_outbox(monkeypatch, leader, ready)
    try:
        assert _settle(lambda: len(calls) > 0)
        leader.clear()
        time.sleep(0.1)
        snapshot = len(calls)
        time.sleep(0.1)
        assert len(calls) == snapshot
    finally:
        stop.set()
        thread.join(timeout=1.0)


def test_outbox_relay_waits_for_ready(monkeypatch):
    leader = threading.Event()
    leader.set()
    ready = threading.Event()
    calls, stop, thread = _start_outbox(monkeypatch, leader, ready)
    try:
        time.sleep(0.05)
        assert calls == []
    finally:
        stop.set()
        thread.join(timeout=1.0)


def _start_reaper(monkeypatch, leader_event, ready_event=None):
    reaper = JobReaper(lambda: FakeSession(), interval_seconds=0.01)
    calls: list[int] = []

    def fake_run_once() -> int:
        calls.append(1)
        return 0

    monkeypatch.setattr(reaper, "run_once", fake_run_once)
    stop = threading.Event()
    kwargs = {"leader_event": leader_event}
    if ready_event is not None:
        kwargs["ready_event"] = ready_event
    thread = threading.Thread(
        target=reaper.run_forever,
        args=(stop,),
        kwargs=kwargs,
        daemon=True,
    )
    thread.start()
    return calls, stop, thread


def test_reaper_idles_when_not_leader(monkeypatch):
    leader = threading.Event()
    ready = threading.Event()
    ready.set()
    calls, stop, thread = _start_reaper(monkeypatch, leader, ready)
    try:
        time.sleep(0.05)
        assert calls == []
    finally:
        stop.set()
        thread.join(timeout=1.0)


def test_reaper_waits_for_ready(monkeypatch):
    leader = threading.Event()
    leader.set()
    ready = threading.Event()
    calls, stop, thread = _start_reaper(monkeypatch, leader, ready)
    try:
        time.sleep(0.05)
        assert calls == []
    finally:
        stop.set()
        thread.join(timeout=1.0)


def test_reaper_stops_when_leadership_lost(monkeypatch):
    leader = threading.Event()
    leader.set()
    calls, stop, thread = _start_reaper(monkeypatch, leader)
    try:
        assert _settle(lambda: len(calls) > 0)
        leader.clear()
        time.sleep(0.1)
        snapshot = len(calls)
        time.sleep(0.1)
        assert len(calls) == snapshot
    finally:
        stop.set()
        thread.join(timeout=1.0)
