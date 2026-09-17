import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status

from agent.config import AgentSettings
from agent.db import create_db_pool
from agent.grpc_client import SaasGrpcClient
from agent.routers import ingest

logger = logging.getLogger(__name__)

HEALTH_CACHE_TTL_SECONDS = 5.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = AgentSettings()
    client = SaasGrpcClient(
        server=settings.saas_grpc_host,
        timeout=settings.grpc_timeout_seconds,
        cache_ttl_seconds=settings.config_cache_ttl_seconds,
    )
    connected = await asyncio.to_thread(client.check_connectivity)
    if connected:
        logger.info("SaaS Backend acessível em %s", settings.saas_grpc_host)
    app.state.saas_client = client
    app.state.saas_connected = connected
    app.state.saas_checked_at = time.monotonic()

    # --- Inicialização TimescaleDB Pool (Issue #35) ---
    db_pool = None
    try:
        db_pool = await create_db_pool(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="postgres",
        )
        logger.info("Pool de conexões TimescaleDB inicializado.")
    except Exception as exc:
        logger.warning(
            "TimescaleDB indisponível no startup (%s); operando sem pool.", exc
        )
    app.state.db_pool = db_pool

    yield

    # --- Teardown Gracioso dos Recursos ---
    if db_pool is not None:
        await db_pool.close()
        logger.info("Pool TimescaleDB encerrado.")

    client.close()
    logger.info("Canal gRPC encerrado.")


app = FastAPI(title="LINX Client Agent API", lifespan=lifespan)

# Registro das rotas da API
app.include_router(ingest.router)


async def _is_saas_connected(fastapi_app: FastAPI) -> bool:
    client = getattr(fastapi_app.state, "saas_client", None)
    if client is None:
        return False

    checked_at = getattr(fastapi_app.state, "saas_checked_at", None)
    now = time.monotonic()
    if checked_at is not None and now - checked_at < HEALTH_CACHE_TTL_SECONDS:
        return fastapi_app.state.saas_connected

    connected = await asyncio.to_thread(client.check_connectivity)
    fastapi_app.state.saas_connected = connected
    fastapi_app.state.saas_checked_at = now
    return connected


@app.get("/health")
async def health(request: Request, response: Response) -> dict:
    connected = await _is_saas_connected(request.app)
    if not connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if connected else "degraded",
        "saas_grpc": connected,
    }
