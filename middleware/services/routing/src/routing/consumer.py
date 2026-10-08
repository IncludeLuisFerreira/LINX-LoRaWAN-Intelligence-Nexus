import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from routing.validation import ValidUplink, validate_message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PendingUplink:
    """Uplink validado aguardando confirmação de publicação.

    Carrega o ``mid``/``qos`` da mensagem MQTT original para que o ack só
    ocorra depois que o RabbitMQ confirmar a publicação. Enquanto o ack não
    acontece, o broker pode reentregar a mensagem (at-least-once).
    """

    uplink: ValidUplink
    mid: int
    qos: int


class MqttConsumer:
    """Consome uplinks MQTT, valida e enfileira os válidos.

    Usa ack manual (``manual_ack=True``) e sessão persistente
    (``clean_session=False``): o ack de uma mensagem só é dado pelo chamador
    após a publicação no RabbitMQ, e mensagens não confirmadas são
    reentregues pelo broker.
    """

    def __init__(
        self,
        *,
        broker_host: str,
        broker_port: int,
        topic: str,
        qos: int,
        max_payload_bytes: int,
        out_queue: queue.Queue,
        client_id: str = "linx-routing",
        connect_max_attempts: int = 5,
        connect_backoff_seconds: float = 1.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.qos = qos
        self.max_payload_bytes = max_payload_bytes
        self.out_queue = out_queue
        self.client_id = client_id
        self.connect_max_attempts = connect_max_attempts
        self.connect_backoff_seconds = connect_backoff_seconds
        self.stop_event = stop_event
        self.client: Any = None

    def on_connect(
        self, client, userdata, connect_flags, reason_code, properties=None
    ) -> None:
        if reason_code == 0:
            logger.info(
                "Conectado ao broker MQTT %s:%s",
                self.broker_host,
                self.broker_port,
            )
            client.subscribe(self.topic, qos=self.qos)
            logger.info("Inscrito no tópico %s (qos=%d)", self.topic, self.qos)
        else:
            logger.error(
                "Falha ao conectar ao broker MQTT: reason_code=%s",
                reason_code,
            )

    def on_message(self, client, userdata, message) -> None:
        try:
            uplink = validate_message(
                message.topic,
                message.payload or b"",
                self.max_payload_bytes,
            )
        except Exception:
            logger.exception(
                "Falha ao validar mensagem MQTT do tópico %s",
                message.topic,
            )
            self.ack(message.mid, message.qos)
            return

        if uplink is None:
            # Mensagem descartada na validação: confirma para o broker não
            # reentregá-la indefinidamente (ack manual).
            self.ack(message.mid, message.qos)
            return

        pending = PendingUplink(
            uplink=uplink, mid=message.mid, qos=message.qos
        )
        try:
            self.out_queue.put_nowait(pending)
        except queue.Full:
            logger.error(
                "Fila de uplinks cheia; descartado do tópico %s",
                message.topic,
            )
            self.ack(message.mid, message.qos)

    def ack(self, mid: int, qos: int) -> None:
        """Confirma a mensagem MQTT após a publicação no RabbitMQ."""
        try:
            self.client.ack(mid, qos)
        except Exception:
            logger.exception("Falha ao confirmar mensagem MQTT mid=%s", mid)

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.info("Desconectado do broker MQTT: reason_code=%s", reason_code)

    def _connect(self) -> bool:
        for attempt in range(1, self.connect_max_attempts + 1):
            if self.stop_event is not None and self.stop_event.is_set():
                logger.info("Encerrando antes de conectar ao broker MQTT")
                return False
            try:
                self.client.connect(self.broker_host, self.broker_port)
                return True
            except (
                OSError,
                ValueError,
                mqtt.WebsocketConnectionError,
            ) as exc:
                logger.error(
                    "Falha ao conectar ao broker MQTT %s:%s "
                    "(tentativa %d/%d): %s",
                    self.broker_host,
                    self.broker_port,
                    attempt,
                    self.connect_max_attempts,
                    exc,
                )
                if attempt == self.connect_max_attempts:
                    logger.error(
                        "Não foi possível conectar ao broker após %d "
                        "tentativas; encerrando",
                        self.connect_max_attempts,
                    )
                    return False
                time.sleep(self.connect_backoff_seconds)
        return False

    def start(self) -> bool:
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            clean_session=False,
            manual_ack=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        if not self._connect():
            return False
        self.client.loop_forever()
        return True

    def stop(self) -> None:
        if self.client is None:
            return
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            logger.exception("Falha ao desconectar do broker MQTT")
