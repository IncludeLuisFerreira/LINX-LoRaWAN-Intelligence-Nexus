from pydantic import BaseModel


class ProvisionResponse(BaseModel):
    """Resposta pública do endpoint de provisionamento Docker."""

    container_id: str
    port: int
    network: str
    image: str
    status: str
    created: bool
    mqtt_topic: str
