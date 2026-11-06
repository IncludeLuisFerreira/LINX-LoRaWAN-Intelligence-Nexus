from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ApplicationStatusValue = Literal[
    "PENDING",
    "PROVISIONING",
    "RUNNING",
    "ERROR",
]


class ApplicationBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=100)


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=100)


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class ApplicationStatusResponse(BaseModel):
    """Estado do container de uma aplicação, lido da ApplicationInstance."""

    model_config = ConfigDict(from_attributes=True)

    app_id: UUID
    status: ApplicationStatusValue
    container_id: str | None = None
    port: int | None = None
    provisioned_at: datetime | None = None
