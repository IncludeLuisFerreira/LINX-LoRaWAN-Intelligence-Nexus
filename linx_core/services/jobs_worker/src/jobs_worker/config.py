from linx_shared.core.config import Settings, require_connection_string
from pydantic import field_validator


class WorkerSettings(Settings):
    rabbitmq_amqp_url: str = ""
    worker_queue: str = "linx.jobs.provisioning"
    worker_concurrency: int = 4
    worker_prefetch: int = 10
    job_max_attempts: int = 3
    job_lock_seconds: int = 60
    job_reaper_interval_seconds: int = 60
    provisioner_grpc_host: str = "docker_provisioner:50052"
    provisioner_grpc_timeout_seconds: float = 10.0

    @field_validator("rabbitmq_amqp_url")
    @classmethod
    def _validate_rabbitmq_amqp_url(cls, value: str) -> str:
        return require_connection_string(
            "RABBITMQ_AMQP_URL",
            value,
            ("guest:guest",),
        )

    @field_validator(
        "worker_concurrency",
        "worker_prefetch",
        "job_max_attempts",
        "job_lock_seconds",
        "job_reaper_interval_seconds",
    )
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("valor deve ser maior que zero")
        return value

    @field_validator("provisioner_grpc_timeout_seconds")
    @classmethod
    def _validate_positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeout deve ser maior que zero")
        return value


settings = WorkerSettings()
