from linx_shared.core.config import Settings


class RoutingSettings(Settings):
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "application/+/device/+/event/up"
    http_timeout_seconds: float = 5.0


settings = RoutingSettings()
