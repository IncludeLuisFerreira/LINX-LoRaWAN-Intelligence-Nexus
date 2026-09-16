import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status

from agent.config import AgentSettings
from agent.grpc_client import SaasGrpcClient

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

    yield

    client.close()
    logger.info("Canal gRPC encerrado.")


app = FastAPI(title="LINX Client Agent API", lifespan=lifespan)


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
