from linx_shared.db.base import engine
from linx_shared.messaging.pika_adapter import open_channel
from sqlalchemy import text

from jobs_worker.config import settings


def check() -> None:
    """Verifica Postgres e RabbitMQ; levanta exceção em caso de falha."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    with open_channel(settings.rabbitmq_amqp_url):
        pass
