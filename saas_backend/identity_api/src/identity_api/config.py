from linx_shared.core.config import Settings


class ChirpStackSettings(Settings):
    chirpstack_host: str = "localhost:8080"
    chirpstack_api_token: str = ""
    chirpstack_device_profile_id: str = ""


settings = ChirpStackSettings()
