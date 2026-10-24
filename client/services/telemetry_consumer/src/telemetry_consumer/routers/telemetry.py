"""Rotas de leitura: listagem REST e stream WebSocket de telemetria.

O plano de dados por tenant exige credencial de serviço (header
`X-Service-Token`). O nginx do dashboard injeta o token server-side nos
proxies `/api` e `/ws`, então o browser nunca conhece o segredo. O `app_id`
continua validado contra o `settings.app_id` do pod (isolamento por pod).
"""

import secrets
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
SERVICE_TOKEN_HEADER = "X-Service-Token"
WS_UNAUTHORIZED = 4401
WS_POLICY_VIOLATION = 1008


def _token_matches(provided: str | None, expected: str) -> bool:
    """Compara em tempo constante. Falha fechada se o token não configurado."""
    if not expected:
        return False
    return secrets.compare_digest(
        (provided or "").encode("utf-8"), expected.encode("utf-8")
    )


@router.get("/telemetry")
async def get_telemetry(
    request: Request,
    dev_eui: str | None = None,
    limit: int = DEFAULT_LIMIT,
    before: str | None = None,
) -> dict[str, Any]:
    settings = request.app.state.settings
    if not _token_matches(
        request.headers.get(SERVICE_TOKEN_HEADER), settings.service_token
    ):
        raise HTTPException(status_code=401, detail="Invalid service token")
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    app_id = settings.app_id
    if before is not None:
        try:
            db.parse_cursor(before)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    clamped = max(MIN_LIMIT, min(MAX_LIMIT, limit))
    items = await db.fetch_telemetry(
        pool, app_id=app_id, dev_eui=dev_eui, limit=clamped, before=before
    )
    next_cursor = db.encode_cursor(items[-1]) if items else None
    return {"items": items, "next_cursor": next_cursor}


async def _reject_ws(websocket: WebSocket, code: int) -> None:
    """Aceita e fecha imediatamente para que o código chegue ao cliente.

    O uvicorn transforma um close antes do accept em rejeição HTTP 403 e
    descarta o código. Aceitar primeiro preserva o contrato 4401/1008, sem
    registrar o socket nem ler mensagens.
    """
    await websocket.accept()
    await websocket.close(code=code)


@router.websocket("/ws/telemetry/{app_id}")
async def ws_telemetry(websocket: WebSocket, app_id: str) -> None:
    settings = websocket.app.state.settings
    # Validação antes de registrar o socket e de ler mensagens. O accept vem
    # antes do close apenas para o uvicorn entregar o código ao cliente.
    if not _token_matches(
        websocket.headers.get(SERVICE_TOKEN_HEADER), settings.service_token
    ):
        await _reject_ws(websocket, WS_UNAUTHORIZED)
        return
    if app_id != settings.app_id:
        await _reject_ws(websocket, WS_POLICY_VIOLATION)
        return
    await websocket.accept()
    broadcaster = websocket.app.state.broadcaster
    await broadcaster.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)
