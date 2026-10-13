from linx_shared.core.config import Settings


class IdentitySettings(Settings):
    chirpstack_host: str = "localhost:8080"
    chirpstack_api_token: str = ""
    chirpstack_use_tls: bool = False
    chirpstack_ca_cert: str | None = None

    rabbitmq_management_url: str = "http://rabbitmq:15672"
    rabbitmq_admin_user: str = "linx"
    rabbitmq_admin_password: str = "changeme"
    rabbitmq_vhost: str = "/"
    rabbitmq_tenant_secret: str = "changeme"
    rabbitmq_amqp_host: str = "rabbitmq:5672"


settings = IdentitySettings()
