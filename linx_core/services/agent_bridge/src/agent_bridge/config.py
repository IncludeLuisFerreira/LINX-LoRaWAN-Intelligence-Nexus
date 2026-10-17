from linx_shared.core.config import Settings


class AgentBridgeSettings(Settings):
    grpc_host: str = "127.0.0.1"
    grpc_port: int = 50051
    agent_service_token: str = ""
    grpc_cert_chain_path: str = ""
    grpc_private_key_path: str = ""
    grpc_ca_cert_path: str = ""


settings = AgentBridgeSettings()
