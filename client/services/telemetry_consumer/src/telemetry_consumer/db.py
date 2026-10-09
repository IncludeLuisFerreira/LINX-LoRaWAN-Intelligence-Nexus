"""Camada de persistencia assincrona no TimescaleDB via asyncpg."""

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


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
    user: str = "telemetry",
    password: str = "changeme",
    database: str = "telemetrydb",
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
    """Busca telemetria recente, opcionalmente filtrada por dev_eui e tempo."""
    query = """
        SELECT time, dev_eui, payload, rssi, snr, app_id, event_type
        FROM telemetry
        WHERE ($2::text IS NULL OR dev_eui = $2)
          AND ($3::timestamptz IS NULL OR time < $3::timestamptz)
        ORDER BY time DESC
        LIMIT $1
    """
    async with pool.acquire() as connection:
        rows = await connection.fetch(query, limit, dev_eui, before)
    return [dict(row) for row in rows]
