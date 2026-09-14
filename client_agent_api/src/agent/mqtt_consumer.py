import logging
import os

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_TOPIC = "application/+/device/+/event/up"


class MqttConsumer:
    def __init__(self) -> None:
        self.broker_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        self.broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self.topic = os.getenv("MQTT_TOPIC", DEFAULT_TOPIC)
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

    def on_message(self, client, userdata, message) -> None:
        logger.info(
            "Uplink recebido no tópico %s: %s", message.topic, message.payload
        )

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.info("Desconectado do broker MQTT: reason_code=%s", reason_code)

    def start(self) -> None:
        self.client.connect(self.broker_host, self.broker_port)
        self.client.loop_forever()

    def stop(self) -> None:
        self.client.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    MqttConsumer().start()


if __name__ == "__main__":
    main()
