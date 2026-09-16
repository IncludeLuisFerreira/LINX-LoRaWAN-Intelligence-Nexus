import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.config import AgentSettings
from agent.grpc_client import SaasGrpcClient

logger = logging.getLogger(__name__)


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

    yield

    client.close()
    logger.info("Canal gRPC encerrado.")


app = FastAPI(title="LINX Client Agent API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "saas_grpc": getattr(app.state, "saas_connected", False),
    }
