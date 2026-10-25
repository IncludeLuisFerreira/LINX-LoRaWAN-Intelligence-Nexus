from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from linx_shared.db.base import get_db
from linx_shared.jobs.constants import JobStatus
from sqlalchemy.orm import Session

from identity_api.jobs import get_tenant_job
from identity_api.schemas import JobErrorResponse, JobStatusResponse

router = APIRouter(prefix="/api/v1/tenant", tags=["Job"])


@router.get(
    "/{tenant_id}/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=JobStatusResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Job not found."}},
)
def get_job_status(
    tenant_id: UUID,
    job_id: UUID,
    db: Session = Depends(get_db),
):
    """Retorna o estado atual de um job do tenant informado."""
    job = get_tenant_job(db, tenant_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found!",
        )
    return JobStatusResponse(
        job_id=job.id,
        type=job.type,
        tenant_id=job.tenant_id,
        subject_id=job.subject_id,
        status=JobStatus(job.status),
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        result=job.result,
        error=(
            JobErrorResponse.model_validate(job.error)
            if job.error is not None
            else None
        ),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
