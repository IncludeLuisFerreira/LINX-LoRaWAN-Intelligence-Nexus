from linx_shared.core.config import Settings, require_connection_string
from pydantic import field_validator


class RoutingSettings(Settings):
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "application/+/device/+/event/up"
    mqtt_qos: int = 1
    mqtt_client_id: str = "linx-routing"
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_connect_max_attempts: int = 5
    mqtt_connect_backoff_seconds: float = 1.0
    rabbit_url: str = ""
    rabbit_exchange_prefix: str = "linx.telemetry"
    rabbit_audit_queue: str = "linx.telemetry.audit"
    max_payload_bytes: int = 65536
    rabbit_connect_max_attempts: int = 5
    rabbit_connect_backoff_seconds: float = 1.0

    @field_validator("rabbit_url")
    @classmethod
    def _validate_rabbit_url(cls, value: str) -> str:
        # RabbitMQ é essencial para o routing; sem credencial real, aborta.
        return require_connection_string("RABBIT_URL", value, ("guest:guest",))


settings = RoutingSettings()
