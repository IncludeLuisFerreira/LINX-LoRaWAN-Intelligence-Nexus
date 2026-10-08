from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    saas_grpc_host: str = "agent_bridge:50051"
    grpc_timeout_seconds: float = 5.0
    config_cache_ttl_seconds: float = 60.0
    tenant_app_url: str = "http://localhost:8002"
    ingest_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
