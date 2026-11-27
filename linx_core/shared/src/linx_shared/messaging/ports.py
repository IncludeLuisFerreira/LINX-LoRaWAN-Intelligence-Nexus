"""Portas de mensageria independentes de biblioteca."""

from __future__ import annotations

from typing import Any, Protocol


class Publisher(Protocol):
    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
        *,
        message_id: str | None = None,
    ) -> None: ...

    def publish_raw(
        self,
        exchange: str,
        routing_key: str,
        body: bytes,
        *,
        message_id: str | None = None,
    ) -> None: ...

    def close(self) -> None: ...


class HealthProbe(Protocol):
    def check(self) -> None: ...
