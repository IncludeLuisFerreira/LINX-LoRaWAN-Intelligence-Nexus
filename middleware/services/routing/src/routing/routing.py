"""Orquestra o ingest de uplinks MQTT para o RabbitMQ."""

import logging
import queue
import signal
import threading

from routing.config import settings
from routing.consumer import MqttConsumer
from routing.envelope import build_envelope, routing_key
from routing.publisher import RabbitPublisher

logger = logging.getLogger(__name__)


class IngestService:
    """Consome uplinks MQTT e publica envelopes no RabbitMQ."""

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        self._publisher_thread: threading.Thread | None = None
        self.consumer = MqttConsumer(
            broker_host=settings.mqtt_broker_host,
            broker_port=settings.mqtt_broker_port,
            topic=settings.mqtt_topic,
            qos=settings.mqtt_qos,
            max_payload_bytes=settings.max_payload_bytes,
            out_queue=self._q,
        )
        self.publisher = RabbitPublisher(
            settings.rabbit_url,
            settings.rabbit_exchange,
            settings.rabbit_connect_max_attempts,
            settings.rabbit_connect_backoff_seconds,
        )

    def _publisher_worker(self) -> None:
        while True:
            try:
                uplink = self._q.get(timeout=1.0)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue
            if uplink is None:
                return
            try:
                key = routing_key(
                    uplink.app_id, uplink.dev_eui, uplink.event_type
                )
                self.publisher.publish(key, build_envelope(uplink))
            except Exception:
                logger.exception(
                    "Falha ao publicar uplink do dev_eui %s",
                    uplink.dev_eui,
                )

    def _start_publisher_thread(self) -> None:
        self._publisher_thread = threading.Thread(
            target=self._publisher_worker, name="publisher", daemon=True
        )
        self._publisher_thread.start()

    def start(self) -> None:
        if not self.publisher.connect():
            return
        self._start_publisher_thread()
        self.consumer.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.consumer.stop()
        self._q.put(None)
        if self._publisher_thread is not None:
            self._publisher_thread.join()
        self.publisher.close()


def main() -> None:  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    service = IngestService()

    def _shutdown(signum, frame):
        logger.info("Sinal %s recebido; encerrando...", signum)
        service.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    service.start()


if __name__ == "__main__":  # pragma: no cover
    main()
