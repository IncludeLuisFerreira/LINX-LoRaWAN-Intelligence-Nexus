from typing import Any, Callable

from fastapi import FastAPI

from telemetry_consumer.config import ConsumerSettings
from telemetry_consumer.routers.telemetry import router as telemetry_router


def create_app(
    settings: ConsumerSettings | None = None,
    *,
    pool_factory: Callable[..., Any] | None = None,
    consumer_factory: Callable[..., Any] | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings or ConsumerSettings()
    app.state.pool_factory = pool_factory
    app.state.consumer_factory = consumer_factory

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(telemetry_router)

    return app


app = create_app()
