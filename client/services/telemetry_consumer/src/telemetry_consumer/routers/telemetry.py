"""Rotas de leitura: listagem REST e stream WebSocket de telemetria."""

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from telemetry_consumer import db

router = APIRouter()

MIN_LIMIT = 1
MAX_LIMIT = 1000
DEFAULT_LIMIT = 100
WS_POLICY_VIOLATION = 1008


@router.get("/telemetry")
async def get_telemetry(
    request: Request,
    dev_eui: str | None = None,
    limit: int = DEFAULT_LIMIT,
    before: str | None = None,
) -> dict[str, Any]:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    clamped = max(MIN_LIMIT, min(MAX_LIMIT, limit))
    items = await db.fetch_telemetry(
        pool, dev_eui=dev_eui, limit=clamped, before=before
    )
    next_cursor = items[-1].get("time") if items else None
    return {"items": items, "next_cursor": next_cursor}


@router.websocket("/ws/telemetry/{app_id}")
async def ws_telemetry(websocket: WebSocket, app_id: str) -> None:
    settings = websocket.app.state.settings
    await websocket.accept()
    if app_id != settings.app_id:
        await websocket.close(code=WS_POLICY_VIOLATION)
        return
    broadcaster = websocket.app.state.broadcaster
    await broadcaster.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)
