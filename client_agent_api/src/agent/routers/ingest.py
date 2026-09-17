"""Router para ingestao de telemetria de dispositivos LoRaWAN."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from agent.db import insert_telemetry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class TelemetryIn(BaseModel):
    """Schema de validacao para payload de telemetria."""

    dev_eui: str = Field(
        ...,
        min_length=1,
        description="Identificador unico do sensor (Device EUI)",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Dicionario JSON contendo as leituras decodificadas",
    )
    rssi: int | None = Field(
        default=None,
        description="Forca do sinal em dBm",
    )
    snr: float | None = Field(
        default=None,
        description="Relacao sinal-ruido em dB",
    )


@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="Ingestao de telemetria de dispositivo",
)
async def ingest_telemetry_endpoint(
    data: TelemetryIn,
    request: Request,
) -> dict[str, bool]:
    """Valida o payload e persiste o registro na hypertable do TimescaleDB."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.error("Pool de conexoes do banco de dados nao inicializado")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection pool unavailable",
        )

    try:
        await insert_telemetry(
            pool=pool,
            dev_eui=data.dev_eui,
            payload=data.payload,
            rssi=data.rssi,
            snr=data.snr,
        )
        return {"ok": True}
    except Exception as exc:
        logger.error(
            "Falha ao persistir telemetria para dev_eui=%s: %s",
            data.dev_eui,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database insertion error",
        ) from exc
