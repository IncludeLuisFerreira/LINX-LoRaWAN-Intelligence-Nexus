from linx_shared.core.config import Settings, require_connection_string
from pydantic import field_validator


class AgentBridgeSettings(Settings):
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        # agent_bridge consulta o catálogo via engine; aborta sem credencial.
        return require_connection_string("DATABASE_URL", value, ("linx:linx",))


settings = AgentBridgeSettings()
