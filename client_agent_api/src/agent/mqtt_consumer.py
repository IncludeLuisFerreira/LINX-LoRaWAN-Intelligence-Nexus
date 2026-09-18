import json
import logging
import os
from typing import Any

import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_TOPIC = "application/+/device/+/event/up"
DEFAULT_INGEST_URL = "http://localhost:8001/ingest"


class MqttConsumer:
    def __init__(self) -> None:
        self.broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        self.broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self.topic = os.getenv("MQTT_TOPIC", DEFAULT_TOPIC)
        self.ingest_url = os.getenv("INGEST_URL", DEFAULT_INGEST_URL)
        self.http_client = httpx.Client(timeout=5.0)
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(
        self, client, userdata, connect_flags, reason_code, properties=None
    ) -> None:
        if reason_code == 0:
            logger.info(
                "Conectado ao broker MQTT %s:%s",
                self.broker_host,
                self.broker_port,
            )
            client.subscribe(self.topic)
            logger.info("Inscrito no tópico %s", self.topic)
        else:
            logger.error(
                "Falha ao conectar ao broker MQTT: reason_code=%s",
                reason_code,
            )

    @staticmethod
    def _parse_payload(raw: bytes) -> dict[str, Any] | None:
        try:
            data = json.loads(raw.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Payload MQTT inválido, ignorando: %s", exc)
            return None

        if (
            not isinstance(data, dict)
            or "dev_eui" not in data
            or "payload" not in data
        ):
            logger.warning(
                "Payload MQTT sem dev_eui/payload obrigatórios, ignorando."
            )
            return None

        telemetry: dict[str, Any] = {
            "dev_eui": data["dev_eui"],
            "payload": data["payload"],
        }
        if "rssi" in data:
            telemetry["rssi"] = data["rssi"]
        if "snr" in data:
            telemetry["snr"] = data["snr"]
        return telemetry

    def on_message(self, client, userdata, message) -> None:
        logger.info(
            "Uplink recebido no tópico %s: %s", message.topic, message.payload
        )
        telemetry = self._parse_payload(message.payload)
        if telemetry is None:
            return

        try:
            response = self.http_client.post(self.ingest_url, json=telemetry)
            response.raise_for_status()
            logger.info(
                "Telemetria encaminhada para /ingest (status=%s)",
                response.status_code,
            )
        except httpx.HTTPError as exc:
            logger.error(
                "Falha ao encaminhar telemetria para /ingest: %s", exc
            )

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.info("Desconectado do broker MQTT: reason_code=%s", reason_code)

    def start(self) -> None:
        self.client.connect(self.broker_host, self.broker_port)
        self.client.loop_forever()

    def stop(self) -> None:
        self.http_client.close()
        self.client.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    MqttConsumer().start()


if __name__ == "__main__":
    main()
