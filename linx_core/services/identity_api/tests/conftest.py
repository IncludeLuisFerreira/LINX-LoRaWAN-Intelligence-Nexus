from collections.abc import Generator

import pytest

from identity_api.dependencies import get_rabbitmq_client
from identity_api.main import app
from tests.fakes import FakeRabbitMQClient


@pytest.fixture(autouse=True)
def rabbitmq() -> Generator[FakeRabbitMQClient, None, None]:
    """Substitui o client da management API do RabbitMQ por um fake."""
    fake = FakeRabbitMQClient()

    def override() -> FakeRabbitMQClient:
        return fake

    app.dependency_overrides[get_rabbitmq_client] = override
    yield fake
    app.dependency_overrides.pop(get_rabbitmq_client, None)
