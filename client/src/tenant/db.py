"""Camada de persistencia assincrona no TimescaleDB via asyncpg."""

import json
import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


async def create_db_pool(
    host: str = "timescaledb",
    port: int = 5432,
    user: str = "tenant",
    password: str = "changeme",
    database: str = "tenantdb",
    min_size: int = 1,
    max_size: int = 10,
) -> asyncpg.Pool:
    """Cria e retorna um pool de conexoes asyncpg."""
    return await asyncpg.create_pool(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        min_size=min_size,
        max_size=max_size,
    )


async def insert_telemetry(
    pool: asyncpg.Pool,
    dev_eui: str,
    payload: dict[str, Any],
    rssi: int | None = None,
    snr: float | None = None,
) -> None:
    """Insere registro na hypertable telemetry via query parametrizada."""
    query = """
        INSERT INTO telemetry (time, dev_eui, payload, rssi, snr)
        VALUES (NOW(), $1, $2::jsonb, $3, $4)
    """
    async with pool.acquire() as connection:
        await connection.execute(
            query,
            dev_eui,
            json.dumps(payload),
            rssi,
            snr,
        )
    logger.info("Telemetria persistida para dev_eui=%s", dev_eui)
