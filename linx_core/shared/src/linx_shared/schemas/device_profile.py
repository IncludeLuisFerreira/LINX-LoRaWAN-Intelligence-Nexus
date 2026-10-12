from uuid import UUID

from pydantic import BaseModel


class DeviceProfileResponse(BaseModel):
    name: str
    id: UUID
