import queue
from unittest.mock import MagicMock

from routing.consumer import PendingUplink
from routing.routing import IngestService
from routing.validation import ValidUplink


def _pending(mid=1, qos=1):
    return PendingUplink(
        uplink=ValidUplink(
            app_id="app1",
            dev_eui="devA",
            event_type="up",
            event={"object": {"t": 20}, "time": "t"},
        ),
        mid=mid,
        qos=qos,
    )


def _service():
    service = IngestService()
    service.consumer = MagicMock()
    service.publisher = MagicMock()
    service.publisher.publish.return_value = True
    return service


def test_publisher_worker_drains_queue_and_acks():
    service = _service()
    seen = []

    def fake_publish(routing_key, body):
        seen.append((routing_key, body))
        service._stop_event.set()
        return True

    service.publisher.publish.side_effect = fake_publish
    service._q.put(_pending(mid=77, qos=1))

    service._publisher_worker()

    assert seen[0][0] == "application.app1.device.devA.up"
    assert seen[0][1]["payload"] == {"t": 20}
    assert service._q.qsize() == 0
    service.consumer.ack.assert_called_once_with(77, 1)


def test_publisher_worker_does_not_ack_on_publish_failure():
    service = _service()

    def fail_then_stop(*_args, **_kwargs):
        service._stop_event.set()
        return False

    service.publisher.publish.side_effect = fail_then_stop
    service._q.put(_pending(mid=9, qos=1))

    service._publisher_worker()

    service.consumer.ack.assert_not_called()


def test_publisher_worker_exits_on_stop_event_without_publishing():
    service = _service()
    service._stop_event.set()
    service._q.put(_pending())

    service._publisher_worker()

    service.publisher.publish.assert_not_called()


def test_publisher_worker_exits_on_sentinel():
    service = _service()
    service._q.put(None)

    service._publisher_worker()

    service.publisher.publish.assert_not_called()


def test_start_connects_publisher_then_starts_thread_then_consumer():
    service = _service()
    order = []
    service.publisher.connect.side_effect = (
        lambda: order.append("connect") or True
    )
    service._start_publisher_thread = lambda: order.append("thread")
    service.consumer.start.side_effect = (
        lambda: order.append("consumer") or True
    )

    assert service.start() is True
    assert order == ["connect", "thread", "consumer"]


def test_start_aborts_when_publisher_cannot_connect():
    service = _service()
    service.publisher.connect.return_value = False
    service._start_publisher_thread = MagicMock()

    assert service.start() is False
    service._start_publisher_thread.assert_not_called()
    service.consumer.start.assert_not_called()


def test_start_aborts_when_stop_event_already_set():
    service = _service()
    service._stop_event.set()

    assert service.start() is False
    service.publisher.connect.assert_not_called()


def test_start_returns_false_when_consumer_fails(monkeypatch):
    service = _service()
    service.publisher.connect.return_value = True
    service.consumer.start.return_value = False
    monkeypatch.setattr(service, "_start_publisher_thread", MagicMock())

    assert service.start() is False
    assert service.stopped is True


def test_stop_stops_consumer_before_closing_publisher():
    service = _service()
    order = []
    service.consumer.stop.side_effect = lambda: order.append("consumer")
    service.publisher.close.side_effect = lambda: order.append("close")

    service.stop()

    assert order == ["consumer", "close"]
    assert service.stopped is True


def test_stop_handles_full_queue_without_blocking():
    service = _service()
    service._q = queue.Queue(maxsize=1)
    service._q.put("occupied")

    service.stop()

    service.publisher.close.assert_called_once()


def test_stop_does_not_close_publisher_when_thread_alive():
    service = _service()
    thread = MagicMock()
    thread.is_alive.return_value = True
    service._publisher_thread = thread

    service.stop()

    service.publisher.close.assert_not_called()


def test_wiring_builds_queue_consumer_and_publisher():
    service = IngestService()
    try:
        assert isinstance(service._q, queue.Queue)
        assert service.consumer.qos == 1
        assert service.consumer.out_queue is service._q
        assert service.consumer.client_id == "linx-routing"
        assert service.publisher is not None
    finally:
        service.publisher.close()
