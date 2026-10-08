from linx_shared.core.config import Settings


class RoutingSettings(Settings):
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "application/+/device/+/event/up"
    mqtt_qos: int = 1
    mqtt_client_id: str = "linx-routing"
    mqtt_connect_max_attempts: int = 5
    mqtt_connect_backoff_seconds: float = 1.0
    rabbit_url: str = "amqp://guest:guest@localhost:5672/%2f"
    rabbit_exchange: str = "linx.telemetry"
    rabbit_audit_queue: str = "linx.telemetry.audit"
    max_payload_bytes: int = 65536
    rabbit_connect_max_attempts: int = 5
    rabbit_connect_backoff_seconds: float = 1.0


settings = RoutingSettings()
