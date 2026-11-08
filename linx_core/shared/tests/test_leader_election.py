import copy
import threading
import time
from datetime import datetime, timedelta, timezone

from linx_shared.coordination.leader import (
    K8sLeaderElector,
    LeaderElectionError,
    LeaseConflictError,
    LeaseNotFoundError,
)


class ManualClock:
    """Clock determinístico: só avança quando o teste chama ``advance``."""

    def __init__(self) -> None:
        self._now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


class FakeLeaseClient:
    """Store em memória com semântica de optimistic concurrency."""

    def __init__(self, clock: ManualClock) -> None:
        self._clock = clock
        self._leases: dict[str, dict] = {}
        self._resource_version = 0
        self._lock = threading.Lock()
        self.fail_replaces = False
        self.transient_error = False

    def _maybe_raise(self) -> None:
        if self.transient_error:
            raise LeaderElectionError("API indisponível")

    def _next_rv(self) -> str:
        self._resource_version += 1
        return str(self._resource_version)

    def get(self, namespace: str, name: str) -> dict | None:
        self._maybe_raise()
        with self._lock:
            lease = self._leases.get(name)
            return copy.deepcopy(lease) if lease is not None else None

    def create(self, namespace: str, name: str, body: dict) -> dict:
        self._maybe_raise()
        with self._lock:
            if name in self._leases:
                raise LeaseConflictError("lease já existe")
            stored = copy.deepcopy(body)
            stored["metadata"]["resourceVersion"] = self._next_rv()
            self._leases[name] = stored
            return copy.deepcopy(stored)

    def replace(self, namespace: str, name: str, body: dict) -> dict:
        self._maybe_raise()
        with self._lock:
            if self.fail_replaces:
                raise LeaseConflictError("falha injetada")
            current = self._leases.get(name)
            if current is None:
                raise LeaseNotFoundError("lease não existe")
            expected = body.get("metadata", {}).get("resourceVersion")
            if expected != current["metadata"].get("resourceVersion"):
                raise LeaseConflictError("resourceVersion divergente")
            stored = copy.deepcopy(body)
            stored["metadata"]["resourceVersion"] = self._next_rv()
            self._leases[name] = stored
            return copy.deepcopy(stored)

    def seed(
        self, name: str, holder: str, renew_time_iso: str, duration: int
    ) -> None:
        with self._lock:
            self._leases[name] = {
                "apiVersion": "coordination.k8s.io/v1",
                "kind": "Lease",
                "metadata": {
                    "name": name,
                    "namespace": "linx",
                    "resourceVersion": self._next_rv(),
                },
                "spec": {
                    "holderIdentity": holder,
                    "leaseDurationSeconds": duration,
                    "acquireTime": renew_time_iso,
                    "renewTime": renew_time_iso,
                },
            }

    def delete(self, name: str) -> None:
        with self._lock:
            self._leases.pop(name, None)

    def holder(self, name: str) -> str | None:
        with self._lock:
            lease = self._leases.get(name)
            return (
                lease["spec"]["holderIdentity"] if lease is not None else None
            )

    def renew_time(self, name: str) -> datetime:
        with self._lock:
            return datetime.fromisoformat(
                self._leases[name]["spec"]["renewTime"]
            )

    def force_holder(
        self, name: str, holder: str, renew_time_iso: str
    ) -> None:
        with self._lock:
            lease = self._leases[name]
            lease["spec"]["holderIdentity"] = holder
            lease["spec"]["renewTime"] = renew_time_iso
            lease["metadata"]["resourceVersion"] = self._next_rv()


class EventLog:
    """Registra callbacks de liderança de forma thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.items: list[str] = []

    def record(self, kind: str) -> None:
        with self._lock:
            self.items.append(kind)

    def wait_for(self, kind: str, count: int, timeout: float = 2.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                seen = self.items.count(kind)
            if seen >= count:
                return True
            time.sleep(0.01)
        return False


def _start(
    elector: K8sLeaderElector,
) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()
    thread = threading.Thread(target=elector.run, args=(stop,), daemon=True)
    thread.start()
    return thread, stop


def test_acquires_leadership_when_lease_absent():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
    )

    thread, stop = _start(elector)
    try:
        assert log.wait_for("started", count=1)
        assert store.holder("jobs-worker") == "pod-0"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_renews_lease_periodically():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
    )

    thread, stop = _start(elector)
    try:
        assert log.wait_for("started", count=1)
        initial = store.renew_time("jobs-worker")
        clock.advance(1.0)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if store.renew_time("jobs-worker") > initial:
                break
            time.sleep(0.01)
        assert store.renew_time("jobs-worker") > initial
        assert store.holder("jobs-worker") == "pod-0"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_does_not_acquire_when_other_holds_unexpired():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    now = clock().isoformat(timespec="microseconds")
    store.seed("jobs-worker", "other", now, duration=15)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
    )

    thread, stop = _start(elector)
    try:
        assert not log.wait_for("started", count=1, timeout=0.3)
        assert store.holder("jobs-worker") == "other"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_loses_leadership_when_renew_fails_past_deadline():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
        on_stopped_leading=lambda: log.record("stopped"),
    )

    thread, stop = _start(elector)
    try:
        assert log.wait_for("started", count=1)
        store.fail_replaces = True
        assert log.wait_for("stopped", count=1)
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_stale_renew_does_not_clobber_holder():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    now = clock().isoformat(timespec="microseconds")
    store.seed("jobs-worker", "pod-0", now, duration=15)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
        on_stopped_leading=lambda: log.record("stopped"),
    )

    thread, stop = _start(elector)
    try:
        assert log.wait_for("started", count=1)
        store.force_holder("jobs-worker", "pod-1", now)
        time.sleep(0.2)
        assert store.holder("jobs-worker") == "pod-1"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_reacquires_after_lease_expires():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    expired = datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat(
        timespec="microseconds"
    )
    store.seed("jobs-worker", "other", expired, duration=15)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
    )

    thread, stop = _start(elector)
    try:
        assert log.wait_for("started", count=1)
        assert store.holder("jobs-worker") == "pod-0"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_lease_deleted_externally_triggers_reacquire():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
        on_stopped_leading=lambda: log.record("stopped"),
    )

    thread, stop = _start(elector)
    try:
        assert log.wait_for("started", count=1)
        store.delete("jobs-worker")
        assert log.wait_for("stopped", count=1)
        assert log.wait_for("started", count=2)
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_network_error_during_acquire_does_not_crash():
    clock = ManualClock()
    store = FakeLeaseClient(clock)
    store.transient_error = True
    log = EventLog()
    elector = K8sLeaderElector(
        client=store,
        identity="pod-0",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=lambda: log.record("started"),
    )

    thread, stop = _start(elector)
    try:
        time.sleep(0.05)
        assert not log.wait_for("started", count=1, timeout=0.2)
        store.transient_error = False
        assert log.wait_for("started", count=1)
        assert store.holder("jobs-worker") == "pod-0"
    finally:
        stop.set()
        thread.join(timeout=2.0)


def test_only_one_leader_at_a_time():
    clock = ManualClock()
    store = FakeLeaseClient(clock)

    class Tracker:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.current = 0
            self.max = 0

        def started(self) -> None:
            with self._lock:
                self.current += 1
                self.max = max(self.max, self.current)

        def stopped(self) -> None:
            with self._lock:
                self.current -= 1

    tracker = Tracker()
    a = K8sLeaderElector(
        client=store,
        identity="pod-a",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=tracker.started,
        on_stopped_leading=tracker.stopped,
    )
    b = K8sLeaderElector(
        client=store,
        identity="pod-b",
        clock=clock,
        retry_period_seconds=0.01,
        on_started_leading=tracker.started,
        on_stopped_leading=tracker.stopped,
    )

    stop = threading.Event()
    ta = threading.Thread(target=a.run, args=(stop,), daemon=True)
    tb = threading.Thread(target=b.run, args=(stop,), daemon=True)
    ta.start()
    tb.start()
    time.sleep(0.3)
    stop.set()
    ta.join(timeout=2.0)
    tb.join(timeout=2.0)

    assert tracker.max == 1
