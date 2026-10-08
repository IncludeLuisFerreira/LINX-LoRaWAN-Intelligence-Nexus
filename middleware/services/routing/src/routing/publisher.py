import json
import logging
import time
from typing import Any

import rabbitpy

logger = logging.getLogger(__name__)


class RabbitPublisher:
    def __init__(
        self,
        url: str,
        exchange: str,
        connect_max_attempts: int = 5,
        backoff_seconds: float = 1.0,
    ) -> None:
        self._url = url
        self._exchange_name = exchange
        self._connect_max_attempts = connect_max_attempts
        self._backoff_seconds = backoff_seconds
        self._connection: Any = None
        self._channel: Any = None
        self._exchange: Any = None

    def _open(self) -> None:
        self._connection = rabbitpy.Connection(self._url)
        self._channel = self._connection.channel()
        self._channel.enable_publisher_confirms()
        self._exchange = rabbitpy.Exchange(
            self._channel,
            self._exchange_name,
            exchange_type="topic",
            durable=True,
        )
        self._exchange.declare()

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
        payload = json.dumps(body).encode()
        for attempt in range(1, self._connect_max_attempts + 1):
            try:
                if not self._is_connected():
                    self.close()
                    self._open()
                message = rabbitpy.Message(
                    self._channel,
                    payload,
                    properties={
                        "content_type": "application/json",
                        "delivery_mode": 2,
                    },
                )
                if message.publish(self._exchange, routing_key):
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
        except Exception as exc:
            logger.warning("erro ao fechar conexão RabbitMQ: %s", exc)
        finally:
            self._connection = None
            self._channel = None
            self._exchange = None
