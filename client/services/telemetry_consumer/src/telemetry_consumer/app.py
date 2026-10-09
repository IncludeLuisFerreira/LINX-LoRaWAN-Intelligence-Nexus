import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi import FastAPI, Request

from telemetry_consumer.broadcaster import Broadcaster
from telemetry_consumer.config import ConsumerSettings
from telemetry_consumer.consumer import RabbitConsumer
from telemetry_consumer.db import create_db_pool, insert_event
from telemetry_consumer.routers.telemetry import router as telemetry_router

logger = logging.getLogger(__name__)


def create_app(
    settings: ConsumerSettings | None = None,
    *,
    pool_factory: Callable[..., Awaitable[Any]] = create_db_pool,
    consumer_factory: Callable[..., Any] = RabbitConsumer,
) -> FastAPI:
    app_settings = settings or ConsumerSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings

        pool: Any = None
        try:
            pool = await pool_factory(
                host=app_settings.db_host,
                port=app_settings.db_port,
                user=app_settings.db_user,
                password=app_settings.db_password,
                database=app_settings.db_name,
            )
            logger.info("Pool TimescaleDB inicializado.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("TimescaleDB indisponivel no startup (%s).", exc)
            pool = None
        app.state.db_pool = pool

        broadcaster = Broadcaster()
        app.state.broadcaster = broadcaster

        async def handler(envelope: dict[str, Any]) -> bool:
            inserted = await insert_event(
                pool,
                event_time=envelope["timestamp"],
                app_id=envelope["app_id"],
                dev_eui=envelope["dev_eui"],
                event_type=envelope["event_type"],
                payload=envelope["payload"],
                rssi=envelope.get("rssi"),
                snr=envelope.get("snr"),
            )
            if inserted:
                await broadcaster.broadcast(
                    {
                        "time": envelope["timestamp"],
                        "app_id": envelope["app_id"],
                        "dev_eui": envelope["dev_eui"],
                        "event_type": envelope["event_type"],
                        "payload": envelope["payload"],
                        "rssi": envelope.get("rssi"),
                        "snr": envelope.get("snr"),
                    }
                )
            return inserted

        consumer = consumer_factory(
            app_settings, asyncio.get_running_loop(), handler
        )
        consumer.start()
        app.state.consumer = consumer

        yield

        consumer.stop()
        if pool is not None:
            await pool.close()
            logger.info("Pool TimescaleDB encerrado.")

    app = FastAPI(lifespan=lifespan)
    app.state.settings = app_settings

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        state = request.app.state
        consumer_state = state.consumer.health()
        return {
            "status": "ok",
            "rabbitmq_connected": consumer_state["rabbitmq_connected"],
            "db_ok": state.db_pool is not None,
            "processed": consumer_state["processed"],
            "failed": consumer_state["failed"],
            "last_processed_at": consumer_state["last_processed_at"],
            "ws_connections": state.broadcaster.count,
        }

    app.include_router(telemetry_router)

    return app


app = create_app()
