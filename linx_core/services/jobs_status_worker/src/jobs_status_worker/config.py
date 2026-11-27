from linx_shared.core.config import Settings, require_connection_string
from linx_shared.jobs.constants import PROVISIONING_STATUS_QUEUE
from pydantic import field_validator


class StatusWorkerSettings(Settings):
    rabbitmq_amqp_url: str = ""
    status_queue: str = PROVISIONING_STATUS_QUEUE
    status_concurrency: int = 2
    status_prefetch: int = 4

    @field_validator("rabbitmq_amqp_url")
    @classmethod
    def _validate_rabbitmq_amqp_url(cls, value: str) -> str:
        return require_connection_string(
            "RABBITMQ_AMQP_URL",
            value,
            ("guest:guest",),
        )

    @field_validator("status_queue")
    @classmethod
    def _validate_status_queue(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("STATUS_QUEUE is required and must not be empty.")
        return cleaned

    @field_validator("status_concurrency", "status_prefetch")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(f"{value!r} deve ser maior que zero")
        return value


settings = StatusWorkerSettings()
