import os
from collections.abc import Generator

import pytest

# Credenciais obrigatórias para o startup dos testes. Os defaults inseguros
# foram removidos do código (#210); aqui as envs são fornecidas antes de
# importar os módulos do serviço, para que a construção de Settings e da
# engine de banco não abortem durante a coleta. Valores de teste apenas.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://linx:ci-db-pass@localhost:5432/linx"
)
os.environ.setdefault("RABBITMQ_ADMIN_PASSWORD", "ci-rabbit-admin-pass")
os.environ.setdefault("RABBITMQ_TENANT_SECRET", "ci-rabbit-tenant-secret")


@pytest.fixture(autouse=True)
def rabbitmq() -> Generator[object, None, None]:
    """Substitui o client da management API do RabbitMQ por um fake."""
    # Import tardio: só os testes que exercitam a aplicação precisam das
    # dependências web (fastapi/chirpstack). Os testes de startup de config
    # dispensam esses pacotes.
    from identity_api.dependencies import get_rabbitmq_client
    from identity_api.main import app
    from tests.fakes import FakeRabbitMQClient

    fake = FakeRabbitMQClient()

    def override() -> FakeRabbitMQClient:
        return fake

    app.dependency_overrides[get_rabbitmq_client] = override
    yield fake
    app.dependency_overrides.pop(get_rabbitmq_client, None)
