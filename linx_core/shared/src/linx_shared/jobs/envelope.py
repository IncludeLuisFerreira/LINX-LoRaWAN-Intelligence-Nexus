from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from linx_shared.jobs.constants import JobStatus


class JobError(BaseModel):
    code: str
    message: str
    retryable: bool
    grpc_code: str | None = None


class JobEnvelope(BaseModel):
    job_id: UUID
    type: str
    version: int = 1
    tenant_id: UUID
    subject_id: UUID
    payload: dict[str, Any]
    attempt: int = 0
    created_at: datetime
    trace_id: UUID | None = None


class JobStatusEvent(BaseModel):
    job_id: UUID
    type: str
    status: JobStatus
    attempt: int
    result: dict[str, Any] | None = None
    error: JobError | None = None
    next_attempt_at: datetime | None = None
    finished_at: datetime | None = None
