from linx_shared.core.config import (
    Settings,
    require_connection_string,
    require_secret,
)
from pydantic import field_validator


class IdentitySettings(Settings):
    environment: str = "development"

    chirpstack_host: str = "localhost:8080"
    chirpstack_api_token: str = ""
    chirpstack_use_tls: bool = False
    chirpstack_ca_cert: str | None = None

    rabbitmq_management_url: str = "http://rabbitmq:15672"
    rabbitmq_admin_user: str = "linx"
    rabbitmq_admin_password: str = ""
    rabbitmq_vhost: str = "/"
    rabbitmq_tenant_secret: str = ""
    rabbitmq_amqp_host: str = "rabbitmq:5672"

    job_max_attempts: int = 3

    # Vazio desabilita o deprovisionamento no delete. O stack que provisiona
    # containers define `docker_provisioner:50052`; stacks sem o serviço
    # continuam podendo excluir aplicações sem depender do Docker.
    provisioner_grpc_host: str = ""
    provisioner_grpc_timeout_seconds: float = 10.0

    @field_validator("provisioner_grpc_host")
    @classmethod
    def _validate_provisioner_grpc_host(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("provisioner_grpc_timeout_seconds")
    @classmethod
    def _validate_provisioner_grpc_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(
                "PROVISIONER_GRPC_TIMEOUT_SECONDS deve ser maior que zero"
            )
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        # identity_api constrói a engine de banco; aborta se faltar credencial.
        return require_connection_string("DATABASE_URL", value, ("linx:linx",))

    @field_validator("rabbitmq_admin_password")
    @classmethod
    def _validate_rabbitmq_admin_password(cls, value: str) -> str:
        return require_secret("RABBITMQ_ADMIN_PASSWORD", value)

    @field_validator("rabbitmq_tenant_secret")
    @classmethod
    def _validate_rabbitmq_tenant_secret(cls, value: str) -> str:
        return require_secret("RABBITMQ_TENANT_SECRET", value)

    @field_validator("job_max_attempts")
    @classmethod
    def _validate_job_max_attempts(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("JOB_MAX_ATTEMPTS deve ser maior que zero")
        return value


settings = IdentitySettings()
