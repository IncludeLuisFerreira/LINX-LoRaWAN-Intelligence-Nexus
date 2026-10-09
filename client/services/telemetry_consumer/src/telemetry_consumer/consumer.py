"""Consumer RabbitMQ com retry, DLQ por tenant e thread dedicada."""

import asyncio
import concurrent.futures
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import rabbitpy

from telemetry_consumer.config import ConsumerSettings

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = (
    "app_id",
    "dev_eui",
    "event_type",
    "payload",
    "timestamp",
)


class RabbitConsumer:
    """Consome telemetria de uma fila por tenant.

    Mensagens validas sao entregues ao handler assincrono com retry; em
    falha definitiva ou payload invalido, o corpo bruto vai para a DLQ.
    Toda mensagem recebe ``ack``.
    """

    def __init__(
        self,
        settings: ConsumerSettings,
        loop: asyncio.AbstractEventLoop | None,
        handler: Callable[[dict[str, Any]], Awaitable[bool]],
        channel: Any = None,
    ) -> None:
        self._settings = settings
        self._loop = loop
        self._handler = handler
        self._channel = channel
        self._connection: Any = None
        self._exchange: Any = None
        self._queue: Any = None
        self._dlq: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._processed = 0
        self._failed = 0
        self._last_processed_at: str | None = None
        self._last_error: str | None = None

    def health(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "rabbitmq_connected": self._is_connected(),
                "processed": self._processed,
                "failed": self._failed,
                "last_processed_at": self._last_processed_at,
                "last_error": self._last_error,
            }

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="telemetry-consumer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._queue is not None:
            try:
                self._queue.stop_consuming()
            except Exception as exc:  # noqa: BLE001
                logger.warning("erro ao parar consumo: %s", exc)
        self.close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _open(self) -> None:
        self._connection = rabbitpy.Connection(self._settings.rabbit_url)
        self._channel = self._connection.channel()
        self._exchange = rabbitpy.Exchange(
            self._channel,
            self._settings.rabbit_exchange,
            exchange_type="topic",
            durable=True,
        )
        self._exchange.declare()
        self._queue = rabbitpy.Queue(
            self._channel,
            self._settings.queue_name,
            durable=True,
            auto_delete=False,
        )
        self._queue.declare()
        self._queue.bind(
            self._exchange, routing_key=self._settings.binding_key
        )
        self._dlq = rabbitpy.Queue(
            self._channel,
            self._settings.dead_letter_queue_name,
            durable=True,
            auto_delete=False,
        )
        self._dlq.declare()
        self._channel.enable_publisher_confirms()

    def _is_connected(self) -> bool:
        if self._connection is None or self._channel is None:
            return False
        if getattr(self._connection, "closed", False) is True:
            return False
        if getattr(self._channel, "closed", False) is True:
            return False
        return True

    def connect(self) -> bool:
        max_attempts = self._settings.rabbit_connect_max_attempts
        for attempt in range(1, max_attempts + 1):
            try:
                self._open()
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "falha ao conectar ao RabbitMQ (tentativa %d/%d): %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                self.close()
                if attempt < max_attempts:
                    if self._stop_event.wait(
                        self._settings.rabbit_connect_backoff_seconds
                    ):
                        return False
        logger.error(
            "não foi possível conectar ao RabbitMQ após %d tentativas",
            max_attempts,
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
            self._exchange = None
            self._queue = None
            self._dlq = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                if not self._is_connected():
                    self.close()
                    if not self.connect():
                        continue
                if self._queue is None:
                    continue
                for message in self._queue.consume(
                    no_ack=False,
                    prefetch=self._settings.rabbit_prefetch_count,
                ):
                    if self._stop_event.is_set():
                        break
                    self._handle_message(message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("conexão com RabbitMQ perdida: %s", exc)
                self._set_error(str(exc))
                self.close()
                if self._stop_event.is_set():
                    break
                self._stop_event.wait(
                    self._settings.rabbit_connect_backoff_seconds
                )

    def _handle_message(self, message: Any) -> None:
        raw_body = message.body
        try:
            envelope = self._parse(raw_body)
            if envelope is None:
                logger.warning("payload inválido; enviando para a DLQ")
                self._dead_letter(raw_body, "payload inválido")
                self._record_failure("payload inválido")
                return
            try:
                self._process_with_retry(envelope)
            except Exception as exc:  # noqa: BLE001
                logger.error("processamento esgotou retries: %s", exc)
                self._dead_letter(raw_body, str(exc))
                self._record_failure(str(exc))
                return
            self._record_processed()
        finally:
            message.ack()

    def _parse(self, raw_body: Any) -> dict[str, Any] | None:
        try:
            data = json.loads(raw_body)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        if any(field not in data for field in REQUIRED_FIELDS):
            return None
        return data

    def _process_with_retry(self, envelope: dict[str, Any]) -> Any:
        total_attempts = 1 + max(0, self._settings.consumer_max_retries)
        last_exc: Exception | None = None
        for attempt in range(1, total_attempts + 1):
            try:
                return self._call_handler(envelope)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "falha ao processar mensagem (tentativa %d/%d): %s",
                    attempt,
                    total_attempts,
                    exc,
                )
                if attempt < total_attempts:
                    time.sleep(self._settings.consumer_retry_backoff_seconds)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("handler falhou sem exceção")

    def _call_handler(self, envelope: dict[str, Any]) -> Any:
        async def invoke() -> Any:
            return await self._handler(envelope)

        coroutine = invoke()
        if self._loop is None:
            return asyncio.run(coroutine)
        try:
            future: concurrent.futures.Future[Any] = (
                asyncio.run_coroutine_threadsafe(coroutine, self._loop)
            )
        except Exception:
            coroutine.close()
            raise
        return future.result()

    def _dead_letter(self, raw_body: Any, reason: str) -> None:
        channel = self._channel
        if channel is None:
            self._set_error(f"DLQ indisponível: {reason}")
            return
        routing_key = self._settings.dead_letter_queue_name
        try:
            if hasattr(channel, "basic_publish"):
                channel.basic_publish(raw_body, "", routing_key)
            else:
                message = rabbitpy.Message(
                    channel,
                    raw_body,
                    properties={
                        "content_type": "application/json",
                        "delivery_mode": 2,
                    },
                )
                message.publish("", routing_key)
        except Exception as exc:  # noqa: BLE001
            logger.error("falha ao publicar na DLQ: %s", exc)
            self._set_error(str(exc))

    def _record_processed(self) -> None:
        with self._state_lock:
            self._processed += 1
            self._last_processed_at = datetime.now(timezone.utc).isoformat()
            self._last_error = None

    def _record_failure(self, reason: str) -> None:
        with self._state_lock:
            self._failed += 1
            self._last_error = reason

    def _set_error(self, reason: str) -> None:
        with self._state_lock:
            self._last_error = reason
