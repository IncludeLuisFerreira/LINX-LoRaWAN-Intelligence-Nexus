import logging
import queue
import time
from typing import Any

import paho.mqtt.client as mqtt

from routing.validation import validate_message

logger = logging.getLogger(__name__)

CONNECT_MAX_ATTEMPTS = 5
CONNECT_BACKOFF_SECONDS = 1.0


class MqttConsumer:
    """Consome uplinks MQTT, valida e enfileira os válidos."""

    def __init__(
        self,
        *,
        broker_host: str,
        broker_port: int,
        topic: str,
        qos: int,
        max_payload_bytes: int,
        out_queue: queue.Queue,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.qos = qos
        self.max_payload_bytes = max_payload_bytes
        self.out_queue = out_queue
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
            return

        if uplink is None:
            return

        try:
            self.out_queue.put_nowait(uplink)
        except queue.Full:
            logger.error(
                "Fila de uplinks cheia; descartado do tópico %s",
                message.topic,
            )

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.info("Desconectado do broker MQTT: reason_code=%s", reason_code)

    def _connect(self) -> bool:
        for attempt in range(1, CONNECT_MAX_ATTEMPTS + 1):
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
                    CONNECT_MAX_ATTEMPTS,
                    exc,
                )
                if attempt == CONNECT_MAX_ATTEMPTS:
                    logger.error(
                        "Não foi possível conectar ao broker após %d "
                        "tentativas; encerrando",
                        CONNECT_MAX_ATTEMPTS,
                    )
                    return False
                time.sleep(CONNECT_BACKOFF_SECONDS)
        return False

    def start(self) -> bool:
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        if not self._connect():
            return False
        self.client.loop_forever()
        return True

    def stop(self) -> None:
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            logger.exception("Falha ao desconectar do broker MQTT")
