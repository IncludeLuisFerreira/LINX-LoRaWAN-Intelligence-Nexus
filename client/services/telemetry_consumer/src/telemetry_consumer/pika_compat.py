"""Camada de compatibilidade da API usada por routing/telemetria sobre Pika.

Existe apenas para migrar os dois serviços sem reescrever o domínio de uma vez.
A implementação usa `pika.Connection`; não depende da biblioteca legada.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from concurrent.futures import Future
from typing import Any, Iterator

import pika

DEFAULT_TIMEOUT_SECONDS = 10.0


class Connection:
    def __init__(self, url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self._closed = threading.Event()
        self._connection = pika.Connection(
            pika.URLParameters(url),
            timeout=timeout,
            on_close_callback=self._on_close,
        )

    def _on_close(self, connection, reason) -> None:
        self._closed.set()

    def channel(self) -> "Channel":
        return Channel(self._connection.channel(), self)

    @property
    def closed(self) -> bool:
        return self._closed.is_set() or not bool(
            getattr(self._connection, "is_open", False)
        )

    def close(self) -> None:
        self._connection.close(timeout=DEFAULT_TIMEOUT_SECONDS)


class Channel:
    def __init__(
        self, channel: Any, connection: Connection | None = None
    ) -> None:
        self._channel = channel
        self._connection = connection
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._confirm_callback = None
        self._return_callback = None
        self._pending: dict[int, Future] = {}
        self._publish_ids: dict[int, str] = {}
        self._returned: set[str] = set()

    @property
    def closed(self) -> bool:
        if self._closed.is_set():
            return True
        if self._connection is not None and self._connection.closed:
            return True
        if getattr(self._channel, "is_closed", False):
            return True
        return not bool(getattr(self._channel, "is_open", False))

    def _fail_pending(self, reason: object) -> None:
        message = f"canal RabbitMQ fechado: {reason}"
        with self._lock:
            futures = list(self._pending.values())
            self._pending.clear()
            self._publish_ids.clear()
        for future in futures:
            if not future.done():
                future.set_exception(
                    pika.exceptions.ChannelWrongStateError(message)
                )

    def enable_publisher_confirms(self) -> None:
        self._channel.confirm_delivery(self._on_confirm)
        self._channel.add_on_return_callback(self._on_return)

    def _on_confirm(self, frame: Any) -> None:
        method = frame.method
        with self._lock:
            tags = [method.delivery_tag]
            if getattr(method, "multiple", False):
                tags = [
                    tag for tag in self._pending if tag <= method.delivery_tag
                ]
            for tag in tags:
                future = self._pending.pop(tag, None)
                publish_id = self._publish_ids.pop(tag, None)
                returned = (
                    publish_id is not None and publish_id in self._returned
                )
                if publish_id is not None:
                    self._returned.discard(publish_id)
                if future is None:
                    continue
                if returned:
                    future.set_exception(pika.exceptions.UnroutableError([]))
                elif isinstance(method, pika.spec.Basic.Ack):
                    future.set_result(True)
                else:
                    future.set_exception(pika.exceptions.NackError([]))

    def _on_return(self, channel, method, properties, body) -> None:
        headers = getattr(properties, "headers", None) or {}
        publish_id = headers.get("x-publish-id")
        if publish_id is not None:
            with self._lock:
                self._returned.add(publish_id)

    def _publish(
        self,
        body: bytes,
        exchange: str,
        routing_key: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        publish_id = uuid.uuid4().hex
        future: Future = Future()
        props_data: dict[str, Any] = {
            "delivery_mode": 2,
            "content_type": "application/json",
        }
        props_data.update(properties or {})
        headers = dict(props_data.pop("headers", {}) or {})
        headers["x-publish-id"] = publish_id
        props = pika.BasicProperties(headers=headers, **props_data)

        def on_publish(tag: int) -> None:
            if future.done():
                return
            with self._lock:
                self._pending[tag] = future
                self._publish_ids[tag] = publish_id

        try:
            self._channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=props,
                mandatory=True,
                on_publish=on_publish,
            )
        except Exception:
            self._returned.discard(publish_id)
            raise
        deadline = time.monotonic() + DEFAULT_TIMEOUT_SECONDS
        while not future.done():
            if self.closed:
                self._fail_pending("canal fechado")
                break
            if time.monotonic() >= deadline:
                self._drop_publish(publish_id)
                raise TimeoutError("broker não confirmou publicação")
            time.sleep(0.02)
        return future.result()

    def _drop_publish(self, publish_id: str) -> None:
        with self._lock:
            tags = [
                tag
                for tag, current_id in self._publish_ids.items()
                if current_id == publish_id
            ]
            for tag in tags:
                self._pending.pop(tag, None)
                self._publish_ids.pop(tag, None)
            self._returned.discard(publish_id)

    def basic_publish(
        self,
        body: bytes,
        exchange: str,
        routing_key: str,
    ) -> bool:
        return self._publish(body, exchange, routing_key)

    def close(self) -> None:
        self._channel.close()


class Exchange:
    def __init__(
        self,
        channel: Channel,
        name: str,
        exchange_type: str = "topic",
        durable: bool = False,
    ) -> None:
        self.channel = channel
        self.name = name
        self.exchange_type = exchange_type
        self.durable = durable

    def declare(self) -> None:
        self.channel._channel.exchange_declare(
            exchange=self.name,
            exchange_type=self.exchange_type,
            durable=self.durable,
        )


class Queue:
    def __init__(
        self,
        channel: Channel,
        name: str,
        durable: bool = False,
        auto_delete: bool = False,
    ) -> None:
        self.channel = channel
        self.name = name
        self.durable = durable
        self.auto_delete = auto_delete
        self._consumer_tag: str | None = None
        self._stop = threading.Event()

    def declare(self) -> None:
        self.channel._channel.queue_declare(
            queue=self.name,
            durable=self.durable,
            auto_delete=self.auto_delete,
        )

    def bind(self, exchange: Exchange, routing_key: str) -> None:
        self.channel._channel.queue_bind(
            queue=self.name,
            exchange=exchange.name,
            routing_key=routing_key,
        )

    def consume(
        self,
        no_ack: bool = False,
        prefetch: int | None = None,
    ) -> Iterator["Delivery"]:
        raw = self.channel._channel
        if prefetch:
            raw.basic_qos(prefetch_count=prefetch)
        messages: queue.Queue[Delivery] = queue.Queue()

        def on_message(channel, method, properties, body) -> None:
            messages.put(Delivery(channel, method, properties, body))

        self._consumer_tag = raw.basic_consume(
            queue=self.name,
            on_message_callback=on_message,
            auto_ack=no_ack,
        )
        while not self._stop.is_set():
            if self.channel.closed:
                raise ConnectionError("canal RabbitMQ fechado")
            try:
                yield messages.get(timeout=0.1)
            except queue.Empty:
                continue

    def stop_consuming(self) -> None:
        self._stop.set()
        if self._consumer_tag is not None:
            try:
                self.channel._channel.basic_cancel(self._consumer_tag)
            except Exception:  # noqa: BLE001
                pass
            self._consumer_tag = None


class Delivery:
    def __init__(self, channel, method, properties, body: bytes) -> None:
        self._channel = channel
        self._method = method
        self.properties = properties
        self.body = body

    def ack(self) -> None:
        self._channel.basic_ack(self._method.delivery_tag)

    def nack(self, requeue: bool = False) -> None:
        self._channel.basic_nack(
            self._method.delivery_tag,
            requeue=requeue,
        )


class Message:
    def __init__(
        self,
        channel: Channel,
        body: bytes,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self._channel = channel
        self.body = body
        self.properties = properties or {}

    def publish(self, exchange: Exchange | str, routing_key: str) -> bool:
        payload = self.body
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload).encode()
        exchange_name = (
            exchange.name if isinstance(exchange, Exchange) else exchange
        )
        return self._channel._publish(
            payload,
            exchange_name,
            routing_key,
            self.properties,
        )
