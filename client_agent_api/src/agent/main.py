import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.config import AgentSettings
from agent.grpc_client import fetch_app_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # type: ignore [call-arg]
    settings = AgentSettings()  # type: ignore [call-arg]
    logger.info("Iniciando Client Agent para app_id=%s", settings.app_id)

    # Executa a chamada gRPC síncrona em thread separada
    app_config = await asyncio.to_thread(
        fetch_app_config,
        app_id=settings.app_id,
        server=settings.saas_grpc_host,
        timeout=settings.grpc_timeout_seconds,
    )

    # Armazena a configuração validada no estado global ASGI
    app.state.app_config = app_config
    logger.info("Client Agent pronto para operar.")

    yield

    logger.info("Encerrando Client Agent.")


app = FastAPI(title="LINX Client Agent API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
