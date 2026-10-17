from linx_shared.core.config import Settings, require_connection_string
from pydantic import field_validator


class AgentBridgeSettings(Settings):
    grpc_host: str = "127.0.0.1"
    grpc_port: int = 50051
    agent_service_token: str = ""
    grpc_cert_chain_path: str = ""
    grpc_private_key_path: str = ""
    grpc_ca_cert_path: str = ""

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        # agent_bridge consulta o catálogo via engine; aborta sem credencial.
        return require_connection_string("DATABASE_URL", value, ("linx:linx",))


settings = AgentBridgeSettings()
