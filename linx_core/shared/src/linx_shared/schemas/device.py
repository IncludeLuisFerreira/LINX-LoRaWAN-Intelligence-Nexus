from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX16 = r"^[0-9a-fA-F]{16}$"
_HEX32 = r"^[0-9a-fA-F]{32}$"


class DeviceCreate(BaseModel):
    dev_eui: str = Field(pattern=_HEX16)
    app_id: UUID
    join_eui: str = Field(pattern=_HEX16)
    app_key: str = Field(pattern=_HEX32)
    device_profile_id: UUID
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("dev_eui", "join_eui", "app_key")
    @classmethod
    def _normalize_hex(cls, value: str) -> str:
        return value.lower()

    @field_validator("nickname", mode="before")
    @classmethod
    def _normalize_nickname(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dev_eui: str
    app_id: UUID
    join_eui: str
    device_profile_id: UUID
    nickname: str | None
    created_at: datetime
    updated_at: datetime


class DeviceUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("nickname", mode="before")
    @classmethod
    def _normalize_nickname(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value
