from linx_shared.core.config import Settings


class AgentBridgeSettings(Settings):
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051


settings = AgentBridgeSettings()
