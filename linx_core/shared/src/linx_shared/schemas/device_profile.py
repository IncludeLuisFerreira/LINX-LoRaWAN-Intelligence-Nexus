from pydantic import BaseModel

from linx_shared.core.uuid4 import UUID4


class DeviceProfileResponse(BaseModel):
    name: str
    id: UUID4
