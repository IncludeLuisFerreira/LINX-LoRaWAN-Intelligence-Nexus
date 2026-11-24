from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    saas_grpc_host: str = "agent_bridge:50051"
    grpc_timeout_seconds: float = 5.0
    config_cache_ttl_seconds: float = 60.0
    grpc_ca_cert_path: str = ""
    grpc_client_cert_path: str = ""
    grpc_client_key_path: str = ""
    # Chave pública RS256 usada para validar JWTs emitidos pelo SaaS.
    jwt_public_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
