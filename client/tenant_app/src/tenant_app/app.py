import os
import secrets

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

SERVICE_TOKEN_HEADER = "X-Service-Token"


class InfoResponse(BaseModel):
    """Dados públicos do tenant; segredos nunca são expostos."""

    app_id: str
    mqtt_topic: str
    db_password_configured: bool


def create_app() -> FastAPI:
    """Monta o app mínimo usado para validar o provisionamento Docker.

    O `/health` fica público para o healthcheck do container. O `/info`
    exige o token de serviço compartilhado, provando que o provisioner
    injetou a credencial correta no ambiente do tenant.
    """
    app = FastAPI(
        title="LINX Tenant App",
        description="Container mínimo provisionado por aplicação.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app_id": os.getenv("APP_ID", ""),
        }

    @app.get("/info", response_model=InfoResponse)
    def info(
        x_service_token: str | None = Header(
            default=None,
            alias=SERVICE_TOKEN_HEADER,
        ),
    ) -> InfoResponse:
        expected = os.getenv("SERVICE_TOKEN", "")
        if not expected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SERVICE_TOKEN is not configured",
            )

        provided = x_service_token or ""
        if not secrets.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid service token",
            )

        return InfoResponse(
            app_id=os.getenv("APP_ID", ""),
            mqtt_topic=os.getenv("MQTT_TOPIC", ""),
            db_password_configured=bool(os.getenv("DB_PASSWORD")),
        )

    return app


app = create_app()
