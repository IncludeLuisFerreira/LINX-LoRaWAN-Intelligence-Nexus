from pydantic_settings import BaseSettings, SettingsConfigDict


class TenantSettings(BaseSettings):
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "tenant"
    db_password: str = "changeme"
    db_name: str = "tenantdb"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
