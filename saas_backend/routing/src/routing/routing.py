"""Roteamento de uplinks MQTT para o Client Agent dono do dispositivo."""

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
import paho.mqtt.client as mqtt
from linx_shared.db.base import SessionLocal
from linx_shared.models.device_route import DeviceRoute
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from routing.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TOPIC = "application/+/device/+/event/up"


def extract_dev_eui(topic: str) -> str | None:
    """Extrai o dev_eui de application/{app_id}/device/{dev_eui}/..."""
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "application" or parts[2] != "device":
        return None
    dev_eui = parts[3]
    return dev_eui or None


def build_ingest_payload(
    dev_eui: str, event: dict[str, Any]
) -> dict[str, Any]:
    """Mapeia um evento de uplink do ChirpStack para o contrato do /ingest."""
    obj = event.get("object")
    payload = obj if isinstance(obj, dict) else {}
    body: dict[str, Any] = {"dev_eui": dev_eui, "payload": payload}
    rx_info = event.get("rxInfo")
    if isinstance(rx_info, list) and rx_info:
        first = rx_info[0]
        if isinstance(first, dict):
            if "rssi" in first:
                body["rssi"] = first["rssi"]
            if "snr" in first:
                body["snr"] = first["snr"]
    return body


def route_uplink(
    dev_eui: str,
    payload: dict[str, Any],
    session_factory: Callable[..., Any] = SessionLocal,
    http_client: httpx.Client | None = None,
) -> bool:
    """Encaminha um uplink ao Client Agent dono do dev_eui.

    Consulta ``device_routes`` por ``dev_eui`` e faz POST para o /ingest do
    Client Agent. Retorna ``False`` (sem lançar) quando não há rota, o endpoint
    é vazio ou a entrega falha.
    """
    try:
        with session_factory() as session:
            route = session.scalar(
                select(DeviceRoute).where(DeviceRoute.dev_eui == dev_eui)
            )
    except SQLAlchemyError:
        logger.exception("Falha ao consultar rota do dev_eui %s", dev_eui)
        return False

    if route is None:
        logger.warning(
            "Sem rota para o dev_eui %s; descartando uplink", dev_eui
        )
        return False

    endpoint = (route.agent_endpoint or "").strip()
    if not endpoint:
        logger.warning(
            "dev_eui %s sem agent_endpoint; descartando uplink", dev_eui
        )
        return False

    url = f"{endpoint.rstrip('/')}/ingest"

    client = http_client
    if client is None:
        client = httpx.Client(timeout=settings.http_timeout_seconds)
    try:
        response = client.post(
            url, json=build_ingest_payload(dev_eui, payload)
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(
            "Falha ao encaminhar uplink do dev_eui %s para %s: %s",
            dev_eui,
            url,
            exc,
        )
        return False
    finally:
        if http_client is None:
            client.close()

    logger.info(
        "Uplink do dev_eui %s roteado para %s (status=%s)",
        dev_eui,
        url,
        response.status_code,
    )
    return True


class UplinkRouter:
    """Consome o tópico MQTT de uplink e roteia via :func:`route_uplink`."""

    def __init__(self, session_factory: Callable[..., Any] = SessionLocal):
        self.broker_host = settings.mqtt_broker_host
        self.broker_port = settings.mqtt_broker_port
        self.topic = settings.mqtt_topic
        self.session_factory = session_factory
        self.http_client = httpx.Client(timeout=settings.http_timeout_seconds)
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
        dev_eui = extract_dev_eui(message.topic)
        if dev_eui is None:
            logger.warning(
                "Não foi possível extrair dev_eui do tópico %s; ignorando",
                message.topic,
            )
            return

        try:
            payload = json.loads(message.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Payload MQTT inválido, ignorando: %s", exc)
            return

        route_uplink(
            dev_eui,
            payload,
            session_factory=self.session_factory,
            http_client=self.http_client,
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
    UplinkRouter().start()


if __name__ == "__main__":
    main()
