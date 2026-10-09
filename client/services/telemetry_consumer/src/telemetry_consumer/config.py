from pydantic_settings import BaseSettings, SettingsConfigDict


class ConsumerSettings(BaseSettings):
    app_id: str = "app-abc123"
    rabbit_url: str = "amqp://guest:guest@localhost:5672/%2f"
    rabbit_exchange: str = "linx.telemetry"
    rabbit_prefetch_count: int = 10
    rabbit_connect_max_attempts: int = 5
    rabbit_connect_backoff_seconds: float = 1.0
    consumer_max_retries: int = 3
    consumer_retry_backoff_seconds: float = 1.0
    consumer_handler_timeout_seconds: float = 30.0
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "tenant"
    db_password: str = "changeme"
    db_name: str = "tenantdb"
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def queue_name(self) -> str:
        return f"linx.telemetry.{self.app_id}"

    @property
    def dead_letter_queue_name(self) -> str:
        return f"linx.telemetry.{self.app_id}.dlq"

    @property
    def binding_key(self) -> str:
        return f"application.{self.app_id}.#"
