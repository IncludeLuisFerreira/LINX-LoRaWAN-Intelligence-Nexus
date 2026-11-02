from collections.abc import Iterator
from functools import lru_cache

from linx_shared.clients.docker_provisioner import DockerProvisionerClient

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.config import settings
from identity_api.rabbitmq_client import RabbitMQClient


@lru_cache
def _build_chirpstack_client() -> ChirpStackClient:
    return ChirpStackClient(
        settings.chirpstack_host,
        settings.chirpstack_api_token,
        use_tls=settings.chirpstack_use_tls,
        ca_cert=settings.chirpstack_ca_cert,
    )


def get_chirpstack_client() -> ChirpStackClient:
    return _build_chirpstack_client()


def close_chirpstack_client() -> None:
    if _build_chirpstack_client.cache_info().currsize:
        _build_chirpstack_client().close()
        _build_chirpstack_client.cache_clear()


@lru_cache
def _build_rabbitmq_client() -> RabbitMQClient:
    return RabbitMQClient(
        settings.rabbitmq_management_url,
        settings.rabbitmq_admin_user,
        settings.rabbitmq_admin_password,
        vhost=settings.rabbitmq_vhost,
    )


def get_rabbitmq_client() -> RabbitMQClient:
    return _build_rabbitmq_client()


def get_docker_provisioner_client() -> (
    Iterator[DockerProvisionerClient | None]
):
    if not settings.provisioner_grpc_host:
        yield None
        return

    client = DockerProvisionerClient(
        target=settings.provisioner_grpc_host,
        service_token=settings.service_token,
        timeout=settings.provisioner_grpc_timeout_seconds,
    )
    try:
        yield client
    finally:
        client.close()
