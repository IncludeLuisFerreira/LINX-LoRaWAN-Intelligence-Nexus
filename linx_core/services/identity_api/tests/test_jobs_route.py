from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from linx_shared.jobs.constants import (
    JOB_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_REQUESTED,
)
from linx_shared.models.job import Job
from linx_shared.models.tenant import Tenant
from sqlalchemy.orm import Session

from identity_api.main import app
from tests.auth import AUTH

client = TestClient(app, headers=AUTH)


def _seed_job(
    db_session: Session,
    *,
    status: str,
    result: dict | None = None,
) -> Job:
    tenant = Tenant(name="Tenant Jobs")
    db_session.add(tenant)
    db_session.flush()

    application_id = uuid4()
    job = Job(
        type=JOB_TYPE_PROVISION_APPLICATION,
        tenant_id=tenant.id,
        subject_id=application_id,
        status=status,
        payload={"application_id": str(application_id)},
        command_exchange=JOB_EXCHANGE,
        command_routing_key=PROVISIONING_REQUESTED,
        deduplication_key=f"seed:{uuid4()}",
        result=result,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _job_url(tenant_id: UUID | str, job_id: UUID | str) -> str:
    return f"/api/v1/tenant/{tenant_id}/jobs/{job_id}"


def test_get_job_returns_result(db_session):
    job = _seed_job(db_session, status="succeeded", result={"port": 8421})

    response = client.get(f"/api/v1/tenant/{job.tenant_id}/jobs/{job.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["result"] == {"port": 8421}


def test_get_job_from_other_tenant_returns_404(db_session):
    job = _seed_job(db_session, status="pending")

    response = client.get(_job_url(uuid4(), job.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found!"}


def test_get_unknown_job_returns_404(db_session):
    job = _seed_job(db_session, status="pending")

    response = client.get(_job_url(job.tenant_id, uuid4()))

    assert response.status_code == 404
