from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = frozenset(
    {
        "changeme",
        "change-me",
        "change-me-in-production",
        "replace-me",
        "replace_me",
        "password",
        "secret",
        "todo",
    }
)


def _require_secret(env_var: str, value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(
            f"{env_var} is required and must not be empty; set it in the "
            "environment before starting the service."
        )
    if cleaned.lower() in _PLACEHOLDER_SECRETS:
        raise ValueError(
            f"{env_var} uses the forbidden placeholder value {cleaned!r}; "
            "set a unique secret in the environment before starting."
        )
    return cleaned


def _require_url(env_var: str, value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(
            f"{env_var} is required and must not be empty; set it in the "
            "environment before starting the service."
        )
    lowered = cleaned.lower()
    if "guest:guest" in lowered:
        raise ValueError(
            f"{env_var} uses the insecure default credential "
            "'guest:guest'; set unique credentials in the environment "
            "before starting."
        )
    if "changeme" in lowered or "change-me" in lowered:
        raise ValueError(
            f"{env_var} contains a placeholder credential; set a real "
            "connection string in the environment before starting."
        )
    return cleaned


class ConsumerSettings(BaseSettings):
    app_id: str = "app-abc123"
    rabbit_url: str = ""
    rabbit_prefetch_count: int = 10
    rabbit_connect_max_attempts: int = 5
    rabbit_connect_backoff_seconds: float = 1.0
    consumer_max_retries: int = 3
    consumer_retry_backoff_seconds: float = 1.0
    consumer_handler_timeout_seconds: float = 30.0
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "tenant"
    db_password: str = ""
    db_name: str = "tenantdb"
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("rabbit_url")
    @classmethod
    def _validate_rabbit_url(cls, value: str) -> str:
        return _require_url("RABBIT_URL", value)

    @field_validator("db_password")
    @classmethod
    def _validate_db_password(cls, value: str) -> str:
        return _require_secret("DB_PASSWORD", value)

    @property
    def rabbit_exchange(self) -> str:
        return f"linx.telemetry.{self.app_id}"

    @property
    def queue_name(self) -> str:
        return f"linx.telemetry.{self.app_id}"

    @property
    def dead_letter_queue_name(self) -> str:
        return f"linx.telemetry.{self.app_id}.dlq"

    @property
    def dead_letter_exchange_name(self) -> str:
        return f"linx.telemetry.{self.app_id}.dlx"

    @property
    def binding_key(self) -> str:
        return f"application.{self.app_id}.#"
