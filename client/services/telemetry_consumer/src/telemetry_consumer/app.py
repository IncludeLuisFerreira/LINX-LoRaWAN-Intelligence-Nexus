from typing import Any, Callable

from fastapi import FastAPI

from telemetry_consumer.config import ConsumerSettings


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

    return app


app = create_app()
