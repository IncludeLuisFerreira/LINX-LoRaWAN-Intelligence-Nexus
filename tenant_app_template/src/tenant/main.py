import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tenant.config import TenantSettings
from tenant.db import create_db_pool
from tenant.routers import ingest

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = TenantSettings()
    pool = None
    try:
        pool = await create_db_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
        )
        logger.info("Pool TimescaleDB inicializado.")
    except Exception as exc:
        logger.warning("TimescaleDB indisponivel no startup (%s).", exc)
    app.state.db_pool = pool

    yield

    if pool is not None:
        await pool.close()
        logger.info("Pool TimescaleDB encerrado.")


app = FastAPI(title="LINX Tenant App Template", lifespan=lifespan)
app.include_router(ingest.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
