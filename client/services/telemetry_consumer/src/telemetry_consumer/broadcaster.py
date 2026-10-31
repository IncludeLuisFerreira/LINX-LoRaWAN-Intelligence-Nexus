"""Broadcaster de mensagens para conexoes WebSocket ativas."""

from typing import Any


class Broadcaster:
    """Mantem o conjunto de WebSockets vivos e difunde mensagens."""

    def __init__(self) -> None:
        self._connections: set[Any] = set()

    @property
    def count(self) -> int:
        return len(self._connections)

    async def register(self, ws: Any) -> None:
        self._connections.add(ws)

    async def unregister(self, ws: Any) -> None:
        self._connections.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                self._connections.discard(ws)
