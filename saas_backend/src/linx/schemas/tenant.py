from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=100)


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=100)


class TenantResponse(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
