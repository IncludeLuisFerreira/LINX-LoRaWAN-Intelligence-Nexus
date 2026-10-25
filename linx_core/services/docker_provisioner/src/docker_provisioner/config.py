from linx_shared.core.config import Settings
from pydantic import field_validator, model_validator


class DockerProvisionerSettings(Settings):
    """Configuração do serviço de provisionamento Docker.

    O `service_token` vem da classe base (`SERVICE_TOKEN`) e é validado no
    startup do servidor gRPC, não na importação do módulo.
    """

    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50052

    provision_image: str = "linx-tenant-app:latest"
    provision_port_min: int = 8100
    provision_port_max: int = 9100
    provision_bind_host: str = "0.0.0.0"
    provision_network_prefix: str = "linx-app"
    provision_container_port: int = 8000

    @field_validator("provision_image", "provision_bind_host")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("provisionamento requer valor não vazio")
        return cleaned

    @field_validator("provision_network_prefix")
    @classmethod
    def _validate_network_prefix(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("PROVISION_NETWORK_PREFIX não pode ser vazio")
        # O prefixo vira parte do nome da rede Docker; evita caracteres que
        # quebram a referência usada pelo daemon.
        if any(char.isspace() for char in cleaned):
            raise ValueError(
                "PROVISION_NETWORK_PREFIX não pode conter espaços"
            )
        return cleaned

    @field_validator("provision_port_min", "provision_port_max")
    @classmethod
    def _validate_port_range_value(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("porta deve estar entre 1 e 65535")
        return value

    @field_validator("provision_container_port")
    @classmethod
    def _validate_container_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("porta do container deve estar entre 1 e 65535")
        return value

    @model_validator(mode="after")
    def _validate_port_range_order(self) -> "DockerProvisionerSettings":
        if self.provision_port_min > self.provision_port_max:
            raise ValueError(
                "PROVISION_PORT_MIN não pode ser maior que "
                "PROVISION_PORT_MAX"
            )
        return self


settings = DockerProvisionerSettings()
