from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from linx_shared.db.base import get_db
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.config import settings as identity_settings
from identity_api.dependencies import close_chirpstack_client
from identity_api.routes.application import router as application_router
from identity_api.routes.device_profile import router as device_profile_router
from identity_api.routes.devices import router as devices_router
from identity_api.routes.jobs import router as jobs_router
from identity_api.routes.tenant import router
from identity_api.routes.user import router as user_router
from identity_api.security import (
    ensure_service_token_configured,
    verify_service_token,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    ensure_service_token_configured()
    yield
    close_chirpstack_client()


def create_app() -> FastAPI:
    """Monta a aplicação com o plano de controle protegido por token.

    O Swagger/OpenAPI só é exposto fora de produção. Todos os routers de
    negócio exigem `X-Service-Token`; `/health` permanece público para os
    healthchecks internos.
    """
    expose_docs = identity_settings.environment != "production"

    application = FastAPI(
        title="LINX SAAS Backend",
        lifespan=lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    auth = [Depends(verify_service_token)]

    @application.get("/health")
    @application.head("/health", include_in_schema=False)
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

    application.include_router(router, dependencies=auth)
    application.include_router(application_router, dependencies=auth)
    application.include_router(jobs_router, dependencies=auth)
    application.include_router(devices_router, dependencies=auth)
    application.include_router(user_router, dependencies=auth)
    application.include_router(device_profile_router, dependencies=auth)

    return application


app = create_app()
