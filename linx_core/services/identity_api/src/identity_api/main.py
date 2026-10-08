from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from linx_shared.db.base import get_db
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.routes.application import router as application_router
from identity_api.routes.devices import (
    close_chirpstack_client,
)
from identity_api.routes.devices import router as devices_router
from identity_api.routes.tenant import router
from identity_api.routes.user import router as user_router
from identity_api.security import ensure_service_token_configured


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    ensure_service_token_configured()
    yield
    close_chirpstack_client()


app = FastAPI(title="LINX SAAS Backend", lifespan=lifespan)


@app.get("/health")
@app.head("/health", include_in_schema=False)
def health(response: Response, db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except SQLAlchemyError:
        db_ok = False

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
    }


app.include_router(router)
app.include_router(application_router)
app.include_router(devices_router)
app.include_router(user_router)
