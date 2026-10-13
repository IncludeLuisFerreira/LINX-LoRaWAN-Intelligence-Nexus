import json
import logging
import time
from typing import Any

import rabbitpy

logger = logging.getLogger(__name__)


class RabbitPublisher:
    """Publica envelopes no exchange de cada tenant.

    O exchange do tenant é `{prefix}.{app_id}`, derivado do segundo
    segmento da routing key (`application.{app_id}...`). A fila de
    auditoria (quando configurada) é ligada com binding `#` a todos os
    exchanges de tenant, agregando a telemetria de toda a plataforma.
    """

    def __init__(
        self,
        url: str,
        exchange_prefix: str,
        connect_max_attempts: int = 5,
        backoff_seconds: float = 1.0,
        audit_queue: str | None = None,
    ) -> None:
        self._url = url
        self._exchange_prefix = exchange_prefix
        self._connect_max_attempts = connect_max_attempts
        self._backoff_seconds = backoff_seconds
        self._audit_queue_name = audit_queue
        self._connection: Any = None
        self._channel: Any = None
        self._audit_queue: Any = None
        self._exchanges: dict[str, Any] = {}

    def _exchange_name(self, app_id: str) -> str:
        return f"{self._exchange_prefix}.{app_id}"

    @staticmethod
    def _app_id_from_routing_key(routing_key: str) -> str:
        parts = routing_key.split(".")
        if len(parts) < 2 or parts[0] != "application" or not parts[1]:
            raise ValueError(f"routing key inválida: {routing_key!r}")
        return parts[1]

    def _open(self) -> None:
        self._connection = rabbitpy.Connection(self._url)
        self._channel = self._connection.channel()
        self._channel.enable_publisher_confirms()
        self._exchanges = {}
        self._audit_queue = None
        if self._audit_queue_name:
            queue = rabbitpy.Queue(
                self._channel,
                self._audit_queue_name,
                durable=True,
                auto_delete=False,
            )
            queue.declare()
            self._audit_queue = queue

    def _ensure_namespace(self, app_id: str) -> Any:
        exchange = self._exchanges.get(app_id)
        if exchange is not None:
            return exchange
        exchange = rabbitpy.Exchange(
            self._channel,
            self._exchange_name(app_id),
            exchange_type="topic",
            durable=True,
        )
        exchange.declare()
        if self._audit_queue is not None:
            try:
                self._audit_queue.bind(exchange, routing_key="#")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "falha ao ligar a fila de auditoria ao exchange %s: %s",
                    self._exchange_name(app_id),
                    exc,
                )
        self._exchanges[app_id] = exchange
        return exchange

    def _is_connected(self) -> bool:
        if self._connection is None or self._channel is None:
            return False
        if getattr(self._connection, "closed", False) is True:
            return False
        if getattr(self._channel, "closed", False) is True:
            return False
        return True

    def connect(self) -> bool:
        for attempt in range(1, self._connect_max_attempts + 1):
            try:
                self._open()
                return True
            except Exception as exc:
                logger.warning(
                    "falha ao conectar ao RabbitMQ (tentativa %d/%d): %s",
                    attempt,
                    self._connect_max_attempts,
                    exc,
                )
                self.close()
                if attempt < self._connect_max_attempts:
                    time.sleep(self._backoff_seconds)

        logger.error(
            "não foi possível conectar ao RabbitMQ após %d tentativas",
            self._connect_max_attempts,
        )
        return False

    def publish(self, routing_key: str, body: dict[str, Any]) -> bool:
        app_id = self._app_id_from_routing_key(routing_key)
        payload = json.dumps(body).encode()
        for attempt in range(1, self._connect_max_attempts + 1):
            try:
                if not self._is_connected():
                    self.close()
                    self._open()
                exchange = self._ensure_namespace(app_id)
                message = rabbitpy.Message(
                    self._channel,
                    payload,
                    properties={
                        "content_type": "application/json",
                        "delivery_mode": 2,
                    },
                )
                if message.publish(exchange, routing_key):
                    return True
                logger.error(
                    "broker não confirmou a publicação na rota %r",
                    routing_key,
                )
            except Exception as exc:
                logger.warning(
                    "falha ao publicar na rota %r (tentativa %d/%d): %s",
                    routing_key,
                    attempt,
                    self._connect_max_attempts,
                    exc,
                )
            self.close()
            if attempt < self._connect_max_attempts:
                time.sleep(self._backoff_seconds)

        logger.error(
            "não foi possível publicar na rota %r após %d tentativas; "
            "mensagem descartada",
            routing_key,
            self._connect_max_attempts,
        )
        return False

    def close(self) -> None:
        try:
            if self._connection is not None:
                self._connection.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("erro ao fechar conexão RabbitMQ: %s", exc)
        finally:
            self._connection = None
            self._channel = None
            self._audit_queue = None
            self._exchanges = {}
