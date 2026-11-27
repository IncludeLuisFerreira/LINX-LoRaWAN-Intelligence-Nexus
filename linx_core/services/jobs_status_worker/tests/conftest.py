import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://linx@127.0.0.1:5432/linx",
)
os.environ.setdefault(
    "RABBITMQ_AMQP_URL",
    "amqp://linx:ci-rabbit-pass@localhost:5672/",
)
