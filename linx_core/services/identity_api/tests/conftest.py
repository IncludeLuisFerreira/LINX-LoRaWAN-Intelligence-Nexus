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
def service_token(monkeypatch) -> None:
    """Configura um SERVICE_TOKEN válido para todos os testes."""
    from linx_shared.core.config import settings as shared_settings

    from tests.auth import TOKEN

    monkeypatch.setattr(shared_settings, "service_token", TOKEN)


@pytest.fixture
def db_session() -> Generator[object, None, None]:
    """Abre uma transação isolada e compartilha a Session com o teste."""
    from linx_shared.db.base import engine, get_db
    from sqlalchemy.orm import Session

    from identity_api.main import app

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


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
