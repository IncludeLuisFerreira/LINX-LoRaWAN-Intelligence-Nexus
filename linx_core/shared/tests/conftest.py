import os
from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

# database_url perdeu o default inseguro (#210). A engine em
# linx_shared.db.base é construída no import, então fornecemos um valor de
# teste parseable antes dos imports que a exercitam. A base Settings continua
# sem validador (routing herda dela e não usa banco).
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://linx:ci-db-pass@localhost:5432/linx"
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Sessão isolada em uma transação revertida ao fim do teste."""
    from linx_shared.db.base import engine

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
