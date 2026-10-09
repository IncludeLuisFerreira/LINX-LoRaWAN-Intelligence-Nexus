"""Camada de persistencia assincrona no TimescaleDB via asyncpg."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Cursor:
    """Cursor de paginacao: timestamp e, opcionalmente, desempate composto."""

    time: str
    dev_eui: str | None = None
    event_type: str | None = None


def parse_cursor(value: str) -> Cursor:
    """Interpreta ``before`` como timestamp ISO ou token composto.

    Token composto: ``"{time}|{dev_eui}|{event_type}"``. Um valor sem ``|``
    e tratado como timestamp ISO puro (compatibilidade retroativa). Levanta
    ``ValueError`` para valor malformado.
    """
    parts = value.split("|")
    if len(parts) == 1:
        time_part, dev_eui, event_type = parts[0], None, None
    elif len(parts) == 3:
        time_part, dev_eui, event_type = parts
    else:
        raise ValueError(f"cursor inválido: {value!r}")
    _parse_iso(time_part)
    return Cursor(time=time_part, dev_eui=dev_eui, event_type=event_type)


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"timestamp inválido: {value!r}") from exc


def encode_cursor(item: dict[str, Any]) -> str | None:
    """Monta o token opaco a partir do ultimo item da pagina."""
    time_value = item.get("time")
    if time_value is None:
        return None
    if isinstance(time_value, datetime):
        time_str = time_value.isoformat()
    else:
        time_str = str(time_value)
    return f"{time_str}|{item.get('dev_eui')}|{item.get('event_type')}"


async def _init_connection(connection: asyncpg.Connection) -> None:
    """Registra codec JSONB para decodificar payload em dict."""
    await connection.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_db_pool(
    host: str = "timescaledb",
    port: int = 5432,
    user: str = "tenant",
    password: str = "changeme",
    database: str = "tenantdb",
    min_size: int = 1,
    max_size: int = 10,
) -> asyncpg.Pool:
    """Cria e retorna um pool de conexoes asyncpg com codec JSONB."""
    return await asyncpg.create_pool(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        min_size=min_size,
        max_size=max_size,
        init=_init_connection,
    )


async def insert_event(
    pool: asyncpg.Pool,
    *,
    event_time: str,
    app_id: str,
    dev_eui: str,
    event_type: str,
    payload: dict[str, Any],
    rssi: int | None,
    snr: float | None,
) -> bool:
    """Insere envelope de telemetria de forma idempotente.

    Retorna True se inseriu, False se duplicata.
    """
    query = """
        INSERT INTO telemetry
            (time, dev_eui, payload, rssi, snr, app_id, event_type)
        VALUES ($1::timestamptz, $2, $3::jsonb, $4, $5, $6, $7)
        ON CONFLICT (dev_eui, time, event_type) DO NOTHING
    """
    async with pool.acquire() as connection:
        status = await connection.execute(
            query,
            event_time,
            dev_eui,
            payload,
            rssi,
            snr,
            app_id,
            event_type,
        )
    inserted = status.endswith("0 1")
    if inserted:
        logger.info("Telemetria persistida para dev_eui=%s", dev_eui)
    return inserted


async def fetch_telemetry(
    pool: asyncpg.Pool,
    *,
    dev_eui: str | None,
    limit: int,
    before: str | None,
) -> list[dict[str, Any]]:
    """Busca telemetria recente, opcionalmente filtrada por dev_eui e tempo.

    ``before`` aceita timestamp ISO puro (``time < $ts``) ou token composto
    (``time < $ts OR (time = $ts AND (dev_eui, event_type) < ($de, $et))``),
    evitando descarte silencioso em timestamps iguais.
    """
    cursor = parse_cursor(before) if before is not None else None
    query = """
        SELECT time, dev_eui, payload, rssi, snr, app_id, event_type
        FROM telemetry
        WHERE ($2::text IS NULL OR dev_eui = $2)
          AND (
            $3::timestamptz IS NULL
            OR time < $3::timestamptz
            OR (
              time = $3::timestamptz
              AND $4::text IS NOT NULL
              AND (dev_eui, event_type) < ($4::text, $5::text)
            )
          )
        ORDER BY time DESC, dev_eui, event_type
        LIMIT $1
    """
    cursor_time = cursor.time if cursor is not None else None
    cursor_dev_eui = cursor.dev_eui if cursor is not None else None
    cursor_event_type = cursor.event_type if cursor is not None else None
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            query,
            limit,
            dev_eui,
            cursor_time,
            cursor_dev_eui,
            cursor_event_type,
        )
    return [dict(row) for row in rows]
