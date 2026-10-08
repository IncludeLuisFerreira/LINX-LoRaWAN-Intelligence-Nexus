import queue
from unittest.mock import MagicMock

from routing.routing import IngestService
from routing.validation import ValidUplink


def _service():
    service = IngestService()
    service.consumer = MagicMock()
    service.publisher = MagicMock()
    service.publisher.publish.return_value = True
    return service


def test_publisher_worker_drains_queue():
    service = _service()
    seen = []

    def fake_publish(routing_key, body):
        seen.append((routing_key, body))
        service._stop_event.set()
        return True

    service.publisher.publish.side_effect = fake_publish
    service._q.put(
        ValidUplink(
            app_id="app1",
            dev_eui="devA",
            event_type="up",
            event={"object": {"t": 20}, "time": "t"},
        )
    )

    service._publisher_worker()

    assert seen[0][0] == "application.app1.device.devA.up"
    assert seen[0][1]["payload"] == {"t": 20}
    assert service._q.qsize() == 0


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
    service.consumer.start.side_effect = lambda: order.append("consumer")

    service.start()

    assert order == ["connect", "thread", "consumer"]


def test_start_aborts_when_publisher_cannot_connect():
    service = _service()
    service.publisher.connect.return_value = False
    service._start_publisher_thread = MagicMock()

    service.start()

    service._start_publisher_thread.assert_not_called()
    service.consumer.start.assert_not_called()


def test_stop_stops_consumer_before_closing_publisher():
    service = _service()
    order = []
    service.consumer.stop.side_effect = lambda: order.append("consumer")
    service.publisher.close.side_effect = lambda: order.append("close")

    service.stop()

    assert order == ["consumer", "close"]


def test_wiring_builds_queue_consumer_and_publisher():
    service = IngestService()
    try:
        assert isinstance(service._q, queue.Queue)
        assert service.consumer.qos == 1
        assert service.consumer.out_queue is service._q
        assert service.publisher is not None
    finally:
        service.publisher.close()
