from datetime import datetime
from uuid import UUID

from linx_shared.jobs.constants import JobStatus
from pydantic import BaseModel


class JobAcceptedResponse(BaseModel):
    job_id: UUID
    application_id: UUID
    status: JobStatus
    created_at: datetime


class JobErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    grpc_code: str | None = None


class JobStatusResponse(BaseModel):
    job_id: UUID
    type: str
    tenant_id: UUID
    subject_id: UUID
    status: JobStatus
    attempts: int
    max_attempts: int
    result: dict | None
    error: JobErrorResponse | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
