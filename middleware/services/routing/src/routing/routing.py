"""Orquestra o ingest de uplinks MQTT para o RabbitMQ."""

import logging
import queue
import signal
import sys
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
        self._join_timeout = (
            settings.rabbit_connect_max_attempts
            * settings.rabbit_connect_backoff_seconds
            + 5.0
        )
        self.consumer = MqttConsumer(
            broker_host=settings.mqtt_broker_host,
            broker_port=settings.mqtt_broker_port,
            topic=settings.mqtt_topic,
            qos=settings.mqtt_qos,
            max_payload_bytes=settings.max_payload_bytes,
            out_queue=self._q,
            client_id=settings.mqtt_client_id,
            connect_max_attempts=settings.mqtt_connect_max_attempts,
            connect_backoff_seconds=settings.mqtt_connect_backoff_seconds,
            stop_event=self._stop_event,
        )
        self.publisher = RabbitPublisher(
            settings.rabbit_url,
            settings.rabbit_exchange,
            settings.rabbit_connect_max_attempts,
            settings.rabbit_connect_backoff_seconds,
            audit_queue=settings.rabbit_audit_queue,
        )

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def _publisher_worker(self) -> None:
        while True:
            if self._stop_event.is_set():
                return
            try:
                pending = self._q.get(timeout=1.0)
            except queue.Empty:
                continue
            if pending is None:
                return
            uplink = pending.uplink
            try:
                key = routing_key(
                    uplink.app_id, uplink.dev_eui, uplink.event_type
                )
                if self.publisher.publish(key, build_envelope(uplink)):
                    self.consumer.ack(pending.mid, pending.qos)
                else:
                    logger.error(
                        "Publicação descartada após esgotar tentativas "
                        "para o dev_eui %s; mensagem MQTT não confirmada",
                        uplink.dev_eui,
                    )
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

    def start(self) -> bool:
        if self._stop_event.is_set():
            return False
        if not self.publisher.connect():
            return False
        if self._stop_event.is_set():
            self.publisher.close()
            return False
        self._start_publisher_thread()
        if not self.consumer.start():
            self._stop_event.set()
            return False
        return True

    def stop(self) -> None:
        self._stop_event.set()
        self.consumer.stop()
        try:
            self._q.put_nowait(None)
        except queue.Full:
            logger.warning(
                "Fila cheia no shutdown; worker drenará sem sentinela"
            )
        if self._publisher_thread is not None:
            self._publisher_thread.join(timeout=self._join_timeout)
            if self._publisher_thread.is_alive():
                logger.error(
                    "Thread publisher não terminou em %ss; conexão RabbitMQ "
                    "não será fechada para não ser usada em corrida",
                    self._join_timeout,
                )
                return
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
    if not service.start() and not service.stopped:
        logger.error("Serviço não iniciou; saindo com código 1")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
