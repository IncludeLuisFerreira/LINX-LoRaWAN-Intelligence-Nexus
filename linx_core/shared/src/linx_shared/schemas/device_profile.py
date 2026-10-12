from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DeviceProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    id: UUID
