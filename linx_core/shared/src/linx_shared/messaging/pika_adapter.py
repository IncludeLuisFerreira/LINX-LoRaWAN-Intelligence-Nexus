"""Adaptador Pika 1.5+ (`pika.Connection`) para publisher e canais."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from typing import Any

import pika

from linx_shared.messaging.connection_manager import PikaConnectionManager

logger = logging.getLogger(__name__)

DEFAULT_CONFIRM_TIMEOUT_SECONDS = 10.0


@contextmanager
def open_channel(url: str) -> Iterator[Any]:
    """Abre um canal one-shot com `pika.Connection` e fecha ao final."""
    manager = PikaConnectionManager(url)
    connection = manager.connect()
    try:
        yield connection.channel()
    finally:
        manager.close()


class PikaPublisher:
    """Publisher confirmado sobre `pika.Connection`.

    Reconstrói a semântica de erro síncrona: mensagem não roteada levanta
    `UnroutableError`; NACK levanta `NackError`.
    """

    def __init__(
        self,
        url: str,
        *,
        confirm_timeout: float = DEFAULT_CONFIRM_TIMEOUT_SECONDS,
    ) -> None:
        self._manager = PikaConnectionManager(
            url,
            timeout=confirm_timeout,
        )
        self._confirm_timeout = confirm_timeout
        self._channel: Any = None
        self._lock = threading.Lock()
        self._waiters: dict[str, Future] = {}
        self._tag_to_id: dict[int, str] = {}
        self._pending: list[str] = []
        self._returned: set[str] = set()

    @staticmethod
    def _is_open(client: Any) -> bool:
        return bool(getattr(client, "is_open", False))

    def _reset(self) -> None:
        self._channel = None
        self._manager.close()

    def _connect(self) -> Any:
        if (
            self._channel is None
            or not self._is_open(self._channel)
            or not self._manager.is_open
        ):
            self._reset()
            connection = self._manager.connect()
            self._channel = connection.channel()
            self._channel.confirm_delivery(self._on_confirm)
            self._channel.add_on_return_callback(self._on_return)
        return self._channel

    def _on_publish(self, delivery_tag: int) -> None:
        with self._lock:
            if self._pending:
                publish_id = self._pending.pop(0)
                self._tag_to_id[delivery_tag] = publish_id

    def _on_return(self, channel, method, properties, body) -> None:
        headers = getattr(properties, "headers", None) or {}
        publish_id = headers.get("x-publish-id")
        if publish_id is not None:
            with self._lock:
                self._returned.add(publish_id)

    def _on_confirm(self, frame) -> None:
        method = frame.method
        with self._lock:
            tags = [method.delivery_tag]
            if getattr(method, "multiple", False):
                tags = [
                    tag
                    for tag in self._tag_to_id
                    if tag <= method.delivery_tag
                ]
            for tag in tags:
                publish_id = self._tag_to_id.pop(tag, None)
                if publish_id is None:
                    continue
                future = self._waiters.pop(publish_id, None)
                returned = publish_id in self._returned
                self._returned.discard(publish_id)
                if future is None:
                    continue
                if returned:
                    future.set_exception(pika.exceptions.UnroutableError([]))
                elif isinstance(method, pika.spec.Basic.Ack):
                    future.set_result(True)
                else:
                    future.set_exception(pika.exceptions.NackError([]))

    def _drop_waiter(self, publish_id: str) -> None:
        with self._lock:
            self._waiters.pop(publish_id, None)
            self._returned.discard(publish_id)
            if publish_id in self._pending:
                self._pending.remove(publish_id)

    def _publish_once(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        content_type: str,
        message_id: str | None,
    ) -> None:
        publish_id = uuid.uuid4().hex
        future: Future = Future()
        with self._lock:
            self._waiters[publish_id] = future
            self._pending.append(publish_id)

        properties = pika.BasicProperties(
            delivery_mode=2,
            content_type=content_type,
            message_id=message_id,
            headers={"x-publish-id": publish_id},
        )
        try:
            channel = self._connect()
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
                mandatory=True,
                on_publish=self._on_publish,
            )
            try:
                future.result(timeout=self._confirm_timeout)
            except FutureTimeout as exc:
                raise TimeoutError(
                    "broker não confirmou a publicação "
                    f"exchange={exchange} routing_key={routing_key}"
                ) from exc
        except Exception:
            self._drop_waiter(publish_id)
            raise

    def _publish_body(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        content_type: str,
        message_id: str | None,
    ) -> None:
        try:
            self._publish_once(
                exchange,
                routing_key,
                body,
                content_type,
                message_id,
            )
        except (
            pika.exceptions.UnroutableError,
            pika.exceptions.NackError,
        ):
            raise
        except (
            pika.exceptions.AMQPConnectionError,
            pika.exceptions.AMQPChannelError,
        ):
            self._reset()
            self._publish_once(
                exchange,
                routing_key,
                body,
                content_type,
                message_id,
            )

    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
        *,
        message_id: str | None = None,
    ) -> None:
        self._publish_body(
            exchange,
            routing_key,
            json.dumps(payload).encode("utf-8"),
            "application/json",
            message_id,
        )

    def publish_raw(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        *,
        message_id: str | None = None,
    ) -> None:
        self._publish_body(
            exchange,
            routing_key,
            body,
            "application/octet-stream",
            message_id,
        )

    def close(self) -> None:
        self._reset()
