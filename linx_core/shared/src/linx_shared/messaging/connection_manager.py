"""Ciclo de vida de conexão Pika, separado da política de mensagens."""

from __future__ import annotations

import logging
import time
from typing import Any

import pika

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRY_DELAY_SECONDS = 1.0


class PikaConnectionManager:
    """Cria conexões Pika com retry limitado e fecha de forma controlada."""

    def __init__(
        self,
        url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._retry_delay = retry_delay
        self._connection: Any = None

    @staticmethod
    def _is_open(client: Any) -> bool:
        return bool(getattr(client, "is_open", False))

    @property
    def is_open(self) -> bool:
        return self._connection is not None and self._is_open(self._connection)

    def connect(self, *, attempts: int = 1) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, max(attempts, 1) + 1):
            try:
                self._connection = pika.Connection(
                    pika.URLParameters(self._url),
                    timeout=self._timeout,
                )
                return self._connection
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "falha ao conectar no RabbitMQ (tentativa %s/%s): %s",
                    attempt,
                    attempts,
                    exc,
                )
                if attempt < attempts:
                    time.sleep(self._retry_delay)
        raise RuntimeError(
            "não foi possível conectar no RabbitMQ"
        ) from last_error

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None and self._is_open(connection):
            try:
                connection.close(timeout=self._timeout)
            except pika.exceptions.AMQPError:
                pass
