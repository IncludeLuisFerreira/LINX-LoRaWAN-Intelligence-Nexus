from uuid import UUID

from linx_shared.jobs.constants import (
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_REQUESTED,
)
from linx_shared.jobs.repository import (
    create_job_with_outbox,
    get_active_job,
    get_job,
)
from linx_shared.models.job import Job
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def create_provisioning_job(
    db: Session,
    tenant_id: UUID,
    application_id: UUID,
) -> Job:
    """Cria (ou reaproveita) o job de provisionamento da aplicação."""
    deduplication_key = f"provisioning.application:{application_id}"

    active = get_active_job(db, deduplication_key)
    if active is not None:
        return active

    try:
        job = create_job_with_outbox(
            db,
            job_type=JOB_TYPE_PROVISION_APPLICATION,
            tenant_id=tenant_id,
            subject_id=application_id,
            payload={"application_id": str(application_id)},
            deduplication_key=deduplication_key,
            exchange=JOB_EXCHANGE,
            routing_key=PROVISIONING_REQUESTED,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        active = get_active_job(db, deduplication_key)
        if active is None:
            raise
        return active

    return job


def get_tenant_job(
    db: Session,
    tenant_id: UUID,
    job_id: UUID,
) -> Job | None:
    """Busca um job garantindo o escopo do tenant."""
    return get_job(db, tenant_id, job_id)
