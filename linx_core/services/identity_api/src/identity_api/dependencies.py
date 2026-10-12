from functools import lru_cache

from identity_api.chirpstack_client import ChirpStackClient
from identity_api.config import settings


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
