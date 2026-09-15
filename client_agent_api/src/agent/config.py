from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    app_id: str = Field(default=...)
    saas_grpc_host: str = "saas:50051"
    grpc_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
