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

    provisioner_grpc_host: str = "localhost:50052"
    provisioner_grpc_timeout_seconds: float = 10.0

    @field_validator("provisioner_grpc_host")
    @classmethod
    def _validate_provisioner_grpc_host(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("PROVISIONER_GRPC_HOST não pode ser vazio")
        return cleaned

    @field_validator("provisioner_grpc_timeout_seconds")
    @classmethod
    def _validate_provisioner_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError(
                "PROVISIONER_GRPC_TIMEOUT_SECONDS deve ser positivo"
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


settings = IdentitySettings()
