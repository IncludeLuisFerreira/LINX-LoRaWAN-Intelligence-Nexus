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
    stop_event = main_module.threading.Event()
    threads = main_module.build_consumer_threads(
        settings, MagicMock(), stop_event
    )

    assert len(threads) == 3
    assert [thread.name for thread in threads] == [
        "status-consumer-0",
        "status-consumer-1",
        "status-consumer-2",
    ]
    assert all(thread.daemon is True for thread in threads)
    for thread in threads:
        args = getattr(thread, "_args")
        assert args[0] == PROVISIONING_STATUS_QUEUE
        assert callable(args[1])
        assert args[2] == settings.rabbitmq_amqp_url
        assert args[3] == settings.status_prefetch
        assert args[4] is stop_event
        assert set(getattr(thread, "_kwargs")) == {"declare"}


def test_consumer_threads_declare_status_topology(monkeypatch):
    settings = _valid_settings(monkeypatch)
    declare_calls = MagicMock()
    monkeypatch.setattr(main_module, "declare_status_topology", declare_calls)
    threads = main_module.build_consumer_threads(
        settings, MagicMock(), main_module.threading.Event()
    )
    channel = object()

    getattr(threads[0], "_kwargs")["declare"](channel)

    declare_calls.assert_called_once_with(channel, settings.status_queue)


def test_consumer_threads_declare_status_topology_with_custom_queue(
    monkeypatch,
):
    settings = _valid_settings(
        monkeypatch, STATUS_QUEUE="linx.jobs.status.custom"
    )
    declare_calls = MagicMock()
    monkeypatch.setattr(main_module, "declare_status_topology", declare_calls)
    threads = main_module.build_consumer_threads(
        settings, MagicMock(), main_module.threading.Event()
    )
    channel = object()

    getattr(threads[0], "_kwargs")["declare"](channel)

    declare_calls.assert_called_once_with(channel, "linx.jobs.status.custom")


def test_declare_topology_uses_status_queue_and_closes(monkeypatch):
    settings = _valid_settings(
        monkeypatch, STATUS_QUEUE="linx.jobs.status.custom"
    )
    monkeypatch.setattr(main_module, "settings", settings)
    channel = object()
    connection = MagicMock()
    connection.channel.return_value = channel
    monkeypatch.setattr(
        main_module.pika,
        "BlockingConnection",
        MagicMock(return_value=connection),
    )
    declarer = MagicMock()
    monkeypatch.setattr(main_module, "declare_status_topology", declarer)

    main_module._declare_topology(
        "amqp://linx:real-rabbit-pass@localhost:5672/"
    )

    declarer.assert_called_once_with(channel, "linx.jobs.status.custom")
    connection.close.assert_called_once_with()


def test_declare_topology_closes_connection_on_declarer_error(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(status_queue=PROVISIONING_STATUS_QUEUE),
    )
    connection = MagicMock()
    monkeypatch.setattr(
        main_module.pika,
        "BlockingConnection",
        MagicMock(return_value=connection),
    )
    monkeypatch.setattr(
        main_module,
        "declare_status_topology",
        MagicMock(side_effect=RuntimeError("declare failed")),
    )

    with pytest.raises(RuntimeError, match="declare failed"):
        main_module._declare_topology(
            "amqp://linx:real-rabbit-pass@localhost:5672/"
        )

    connection.close.assert_called_once_with()


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
    wait_for_dependencies = MagicMock()
    declare_topology = MagicMock()
    signal_handler = MagicMock()
    monkeypatch.setattr(
        main_module, "_wait_for_dependencies", wait_for_dependencies
    )
    monkeypatch.setattr(main_module, "_declare_topology", declare_topology)
    monkeypatch.setattr(main_module.threading, "Event", lambda: stop_event)
    monkeypatch.setattr(main_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(main_module.signal, "signal", signal_handler)

    main_module.main()

    assert len(created) == 1
    assert created[0].started is True
    assert created[0].joined is True
    wait_for_dependencies.assert_called_once_with()
    declare_topology.assert_called_once_with(settings.rabbitmq_amqp_url)
    signalled = {call.args[0] for call in signal_handler.call_args_list}
    assert signalled == {
        main_module.signal.SIGTERM,
        main_module.signal.SIGINT,
    }
