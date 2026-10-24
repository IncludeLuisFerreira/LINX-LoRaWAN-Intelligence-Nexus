import os
from collections.abc import Callable, Generator
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://linx@127.0.0.1:5432/linx",
)
os.environ.setdefault(
    "RABBITMQ_AMQP_URL",
    "amqp://rabbit@127.0.0.1:5672/",
)
os.environ.setdefault(
    "SERVICE_TOKEN",
    "test-service-token-0123456789abcdef",
)
os.environ.setdefault("PROVISIONER_GRPC_HOST", "127.0.0.1:50052")


@pytest.fixture
def connection() -> Generator[Any, None, None]:
    from linx_shared.db.base import engine

    connection = engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def session_factory(connection: Any) -> Any:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture
def db_session(session_factory: Any) -> Generator[Any, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def job_factory(db_session: Any) -> Callable[..., Any]:
    from linx_shared.jobs.constants import (
        JOB_EXCHANGE,
        JOB_TYPE_PROVISION_APPLICATION,
        PROVISIONING_REQUESTED,
        JobStatus,
    )
    from linx_shared.models.job import Job
    from linx_shared.models.tenant import Tenant

    def create(
        *,
        status: str = JobStatus.PENDING.value,
        attempts: int = 0,
        max_attempts: int = 3,
        locked_until: datetime | None = None,
        next_attempt_at: datetime | None = None,
        job_type: str = JOB_TYPE_PROVISION_APPLICATION,
        subject_id: UUID | None = None,
        command_exchange: str = JOB_EXCHANGE,
        command_routing_key: str = PROVISIONING_REQUESTED,
        tenant_id: UUID | None = None,
    ) -> Any:
        if tenant_id is None:
            tenant = Tenant(name=f"tenant-{uuid4()}")
            db_session.add(tenant)
            db_session.flush()
            tenant_id = tenant.id

        subject_id = subject_id or uuid4()
        job = Job(
            type=job_type,
            tenant_id=tenant_id,
            subject_id=subject_id,
            payload={"application_id": str(subject_id)},
            command_exchange=command_exchange,
            command_routing_key=command_routing_key,
            deduplication_key=f"test:{uuid4()}",
            status=status,
            attempts=attempts,
            max_attempts=max_attempts,
            locked_until=locked_until,
            next_attempt_at=next_attempt_at,
        )
        db_session.add(job)
        db_session.flush()
        return job

    return create
