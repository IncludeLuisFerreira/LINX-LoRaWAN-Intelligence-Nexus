"""Roteamento de uplinks MQTT para o Client Agent dono do dispositivo."""

import ipaddress
import json
import logging
import queue
import re
import signal
import socket
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import paho.mqtt.client as mqtt
from linx_shared.db.base import SessionLocal
from linx_shared.models.device_route import DeviceRoute
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from routing.config import settings

logger = logging.getLogger(__name__)

NUM_OF_WORKERS = 4
CONNECT_MAX_ATTEMPTS = 5
CONNECT_BACKOFF_SECONDS = 1.0
POST_MAX_ATTEMPTS = 3
POST_RETRY_BACKOFF_SECONDS = 0.5
WORKER_JOIN_BUFFER_SECONDS = 5.0
BLOCKED_METADATA_HOST = "169.254.169.254"
_USERINFO_PATTERN = re.compile(r"(?<=://)[^/@\s]+(?=@)")


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
    if not isinstance(obj, dict):
        logger.warning(
            "Evento sem 'object' para o dev_eui %s; payload vazio", dev_eui
        )
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


def redact_url(url: str) -> str:
    """Mascara a userinfo embutida na URL para logging seguro."""
    parts = urlsplit(url)
    if parts.username is None and parts.password is None:
        return url
    host = parts.hostname or ""
    netloc = host
    if parts.port is not None:
        netloc = f"{host}:{parts.port}"
    return urlunsplit(
        (
            parts.scheme,
            f"***@{netloc}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


def _scrub(text: str) -> str:
    """Remove userinfo embutida em quaisquer URLs dentro de um texto."""
    return _USERINFO_PATTERN.sub("***", text)


def _canonical_ipv4(host: str) -> str | None:
    """Converte formas aceitas pelo libc (decimal/octal) em dotted-quad."""
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return socket.inet_ntoa(packed)


def _is_blocked_host(host: str) -> bool:
    normalized = host.strip("[]").lower()
    if normalized == BLOCKED_METADATA_HOST:
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return address.is_link_local


def _endpoint_error(endpoint: str) -> str | None:
    parts = urlsplit(endpoint)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return f"esquema inválido {scheme!r}"
    host = (parts.hostname or "").lower()
    if not host:
        return "host ausente"
    host = host.rstrip(".")
    if not host:
        return "host ausente"
    canonical = _canonical_ipv4(host)
    if canonical is not None:
        if canonical != host:
            return f"host não canônico {host!r}"
        if _is_blocked_host(canonical):
            return f"host bloqueado (link-local) {canonical!r}"
    elif _is_blocked_host(host):
        return f"host bloqueado (link-local) {host!r}"
    allowlist = settings.agent_endpoint_allowlist
    if allowlist and host not in {item.lower() for item in allowlist}:
        return f"host {host!r} fora da allowlist"
    return None


def _transient_error(exc: Exception) -> tuple[bool, Exception]:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500, exc
    if isinstance(exc, httpx.TransportError):
        return True, exc
    return False, exc


def _post_with_retry(
    client: httpx.Client,
    url: str,
    body: dict[str, Any],
    dev_eui: str,
) -> httpx.Response | None:
    safe_url = redact_url(url)
    for attempt in range(1, POST_MAX_ATTEMPTS + 1):
        try:
            response = client.post(url, json=body)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            retryable, detail = _transient_error(exc)
            if not retryable or attempt == POST_MAX_ATTEMPTS:
                logger.error(
                    "Falha ao encaminhar uplink do dev_eui %s para %s: %s",
                    dev_eui,
                    safe_url,
                    detail,
                )
                return None
            logger.warning(
                "Falha transitória ao encaminhar uplink do dev_eui %s para "
                "%s (tentativa %d/%d); repetindo",
                dev_eui,
                safe_url,
                attempt,
                POST_MAX_ATTEMPTS,
            )
            time.sleep(POST_RETRY_BACKOFF_SECONDS)
    return None


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
                select(DeviceRoute).where(
                    func.lower(DeviceRoute.dev_eui) == dev_eui.lower()
                )
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

    invalid = _endpoint_error(endpoint)
    if invalid is not None:
        logger.error(
            "agent_endpoint do dev_eui %s inválido (%s); descartando uplink",
            dev_eui,
            invalid,
        )
        return False

    url = f"{endpoint.rstrip('/')}/ingest"

    client = http_client
    if client is None:
        client = httpx.Client(timeout=settings.http_timeout_seconds)
    try:
        response = _post_with_retry(
            client, url, build_ingest_payload(dev_eui, payload), dev_eui
        )
        if response is None:
            return False
    finally:
        if http_client is None:
            client.close()

    logger.info(
        "Uplink do dev_eui %s roteado para %s (status=%s)",
        dev_eui,
        redact_url(url),
        response.status_code,
    )
    return True


class UplinkRouter:
    """Consome o tópico MQTT de uplink e roteia via :func:`route_uplink`."""

    def __init__(
        self,
        session_factory: Callable[..., Any] = SessionLocal,
        num_workers: int = NUM_OF_WORKERS,
    ):
        self.broker_host = settings.mqtt_broker_host
        self.broker_port = settings.mqtt_broker_port
        self.topic = settings.mqtt_topic
        self.session_factory = session_factory
        self.num_workers = num_workers
        self._stop_event = threading.Event()
        self._workers: list[threading.Thread] = []
        self._q: queue.Queue[tuple[str, bytes] | None] = queue.Queue(
            maxsize=1000
        )
        self._join_timeout = (
            settings.http_timeout_seconds * POST_MAX_ATTEMPTS
            + WORKER_JOIN_BUFFER_SECONDS
        )
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
        size = len(message.payload or b"")
        if size > settings.max_payload_bytes:
            logger.error(
                "payload de %d bytes excede o limite de %d; descartado do "
                "tópico %s",
                size,
                settings.max_payload_bytes,
                message.topic,
            )
            return
        try:
            self._q.put_nowait((message.topic, message.payload))
        except queue.Full:
            logger.error(
                "Fila de uplinks cheia (%d); descartado do tópico %s",
                self._q.maxsize,
                message.topic,
            )

    def _handle_uplink(self, topic: str, payload: bytes) -> None:
        dev_eui = extract_dev_eui(topic)
        if dev_eui is None:
            logger.warning(
                "Não foi possível extrair dev_eui do tópico %s; ignorando",
                topic,
            )
            return

        try:
            event = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Payload MQTT inválido, ignorando: %s", exc)
            return

        if not isinstance(event, dict):
            logger.warning(
                "Payload MQTT não é um objeto JSON, ignorando: %r", event
            )
            return

        route_uplink(
            dev_eui,
            event,
            session_factory=self.session_factory,
            http_client=self.http_client,
        )

    def _worker(self) -> None:
        while True:
            try:
                item = self._q.get(timeout=1.0)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue
            if item is None:
                self._q.task_done()
                return
            topic, payload = item
            try:
                self._handle_uplink(topic, payload)
            except Exception:
                logger.exception(
                    "Falha ao processar uplink do tópico %s", topic
                )
            finally:
                self._q.task_done()

    def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ) -> None:
        logger.info("Desconectado do broker MQTT: reason_code=%s", reason_code)

    def _start_workers(self) -> None:
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker, name=f"uplink-worker-{i}", daemon=True
            )
            worker.start()
            self._workers.append(worker)

    def _connect(self) -> bool:
        for attempt in range(1, CONNECT_MAX_ATTEMPTS + 1):
            if self._stop_event.is_set():
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

    def _drain_queue(self) -> None:
        for _ in self._workers:
            self._q.put(None)

    def start(self) -> None:
        self._start_workers()
        if not self._connect():
            return
        self.client.loop_forever()

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            logger.exception("Falha ao desconectar do broker MQTT")
        self._drain_queue()
        for worker in self._workers:
            worker.join(timeout=self._join_timeout)
            if worker.is_alive():
                logger.error("Worker %s não terminou a tempo", worker.name)
        self.http_client.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    router = UplinkRouter()

    def _shutdown(signum, frame):
        logger.info("Sinal %s recebido; encerrando...", signum)
        router.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    router.start()


if __name__ == "__main__":
    main()
