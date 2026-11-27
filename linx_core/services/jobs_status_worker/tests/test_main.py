from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_STATUS_QUEUE,
    JobStatus,
)
from linx_shared.jobs.consumer import InvalidMessageError
from linx_shared.jobs.envelope import JobStatusEvent

from jobs_status_worker import main as main_module
from jobs_status_worker.config import StatusWorkerSettings


def _valid_settings(monkeypatch, **env):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL",
        "amqp://linx:real-rabbit-pass@localhost:5672/",
    )
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return StatusWorkerSettings(_env_file=None)


def _event(job_id):
    return JobStatusEvent(
        job_id=job_id,
        type=JOB_TYPE_PROVISION_APPLICATION,
        status=JobStatus.RUNNING,
        attempt=1,
    )


def test_parse_valid_status_event():
    event = _event("00000000-0000-0000-0000-000000000001")

    parsed = main_module._parse_status_event(event.model_dump_json().encode())

    assert parsed == event


def test_malformed_status_event_is_invalid_message():
    with pytest.raises(InvalidMessageError):
        main_module._parse_status_event(b'{"job_id": "not-a-uuid"}')


def test_status_callback_parses_and_processes():
    processed = []
    processor = MagicMock()
    processor.process.side_effect = processed.append
    callback = main_module.build_status_callback(processor)
    event = _event("00000000-0000-0000-0000-000000000001")

    callback(event.model_dump_json().encode())

    assert processed == [event]


def test_build_consumer_threads_uses_status_queue_and_concurrency(
    monkeypatch,
):
    settings = _valid_settings(monkeypatch, STATUS_CONCURRENCY="3")
    threads = main_module.build_consumer_threads(
        settings, MagicMock(), main_module.threading.Event()
    )

    assert len(threads) == 3
    assert [thread.name for thread in threads] == [
        "status-consumer-0",
        "status-consumer-1",
        "status-consumer-2",
    ]
    assert all(
        getattr(thread, "_args")[0] == PROVISIONING_STATUS_QUEUE
        for thread in threads
    )
    assert all(thread.daemon is True for thread in threads)


def test_wait_for_dependencies_retries_then_succeeds(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "check", lambda: calls.append("check"))
    engine = MagicMock()
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module.time, "sleep", lambda _: None)

    main_module._wait_for_dependencies()

    assert calls == ["check"]
    engine.connect.assert_called_once()


def test_wait_for_dependencies_raises_after_all_attempts(monkeypatch):
    attempts = []

    def failing_check():
        attempts.append(1)
        raise RuntimeError("db down")

    monkeypatch.setattr(main_module, "check", failing_check)
    monkeypatch.setattr(main_module.time, "sleep", lambda _: None)

    with pytest.raises(
        RuntimeError, match="dependencies did not become ready"
    ):
        main_module._wait_for_dependencies()

    assert len(attempts) == main_module.READY_ATTEMPTS


def test_main_starts_threads_and_stops(monkeypatch):
    import threading

    settings = SimpleNamespace(
        status_queue=PROVISIONING_STATUS_QUEUE,
        status_concurrency=1,
        status_prefetch=4,
        rabbitmq_amqp_url="amqp://linx:real-rabbit-pass@localhost:5672/",
    )
    stop_event = threading.Event()
    stop_event.set()
    created = []

    class FakeThread:
        def __init__(self, *args, **kwargs):
            self.started = False
            self.joined = False
            created.append(self)

        def start(self):
            self.started = True

        def join(self, timeout=None):
            self.joined = True

    monkeypatch.setattr(main_module, "StatusWorkerSettings", lambda: settings)
    monkeypatch.setattr(main_module, "SessionLocal", MagicMock())
    monkeypatch.setattr(main_module, "_wait_for_dependencies", lambda: None)
    monkeypatch.setattr(main_module, "_declare_topology", lambda *a: None)
    monkeypatch.setattr(main_module.threading, "Event", lambda: stop_event)
    monkeypatch.setattr(main_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(main_module.signal, "signal", lambda *a: None)

    main_module.main()

    assert len(created) == 1
    assert created[0].started is True
    assert created[0].joined is True
