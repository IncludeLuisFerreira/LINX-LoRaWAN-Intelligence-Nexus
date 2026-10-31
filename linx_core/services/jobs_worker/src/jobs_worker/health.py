import pika
from linx_shared.db.base import engine
from sqlalchemy import text

from jobs_worker.config import settings


def check() -> None:
    """Verifica Postgres e RabbitMQ; levanta exceção em caso de falha."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    rabbit = pika.BlockingConnection(
        pika.URLParameters(settings.rabbitmq_amqp_url)
    )
    try:
        rabbit.channel()
    finally:
        rabbit.close()
