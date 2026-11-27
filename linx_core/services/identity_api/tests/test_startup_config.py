import pytest
from pydantic import ValidationError

from identity_api.config import IdentitySettings

_VALID_DB = "postgresql+psycopg://u:p@h:5432/db"


def _valid_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _VALID_DB)
    monkeypatch.setenv("RABBITMQ_ADMIN_PASSWORD", "real-admin-pass")
    monkeypatch.setenv("RABBITMQ_TENANT_SECRET", "real-tenant-secret")


def test_startup_accepts_full_config(monkeypatch):
    _valid_env(monkeypatch)
    settings = IdentitySettings(_env_file=None)
    assert settings.database_url == _VALID_DB
    assert settings.rabbitmq_admin_password == "real-admin-pass"
    assert settings.rabbitmq_tenant_secret == "real-tenant-secret"
    assert settings.job_max_attempts == 3


def test_startup_rejects_missing_rabbitmq_admin_password(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("RABBITMQ_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError, match="RABBITMQ_ADMIN_PASSWORD"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_placeholder_rabbitmq_admin_password(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("RABBITMQ_ADMIN_PASSWORD", "changeme")
    with pytest.raises(ValidationError, match="RABBITMQ_ADMIN_PASSWORD"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_missing_tenant_secret(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("RABBITMQ_TENANT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="RABBITMQ_TENANT_SECRET"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_missing_database_url(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_default_database_credentials(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://linx:linx@localhost:5432/linx",
    )
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        IdentitySettings(_env_file=None)


def test_chirpstack_tls_is_enabled_by_default(monkeypatch):
    _valid_env(monkeypatch)

    settings = IdentitySettings(_env_file=None)

    assert settings.chirpstack_use_tls is True


def test_production_rejects_chirpstack_without_tls(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CHIRPSTACK_USE_TLS", "false")

    with pytest.raises(ValidationError, match="CHIRPSTACK_USE_TLS"):
        IdentitySettings(_env_file=None)


@pytest.mark.parametrize("environment", ["Production", " production "])
def test_production_guard_ignores_case_and_spaces(monkeypatch, environment):
    _valid_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("CHIRPSTACK_USE_TLS", "false")

    with pytest.raises(ValidationError, match="CHIRPSTACK_USE_TLS"):
        IdentitySettings(_env_file=None)


def test_development_allows_chirpstack_without_tls(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CHIRPSTACK_USE_TLS", "false")

    settings = IdentitySettings(_env_file=None)

    assert settings.chirpstack_use_tls is False


def test_startup_rejects_non_positive_job_max_attempts(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("JOB_MAX_ATTEMPTS", "0")

    with pytest.raises(ValidationError, match="JOB_MAX_ATTEMPTS"):
        IdentitySettings(_env_file=None)


def test_startup_accepts_provisioner_token_when_host_set(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "docker_provisioner:50052")
    monkeypatch.setenv(
        "PROVISIONER_SERVICE_TOKEN", "test-provisioner-token-0123456789abcdef"
    )
    settings = IdentitySettings(_env_file=None)
    assert (
        settings.provisioner_service_token
        == "test-provisioner-token-0123456789abcdef"
    )


def test_startup_rejects_missing_provisioner_token_when_host_set(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "docker_provisioner:50052")
    with pytest.raises(ValidationError, match="PROVISIONER_SERVICE_TOKEN"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_short_provisioner_token_when_host_set(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "docker_provisioner:50052")
    monkeypatch.setenv("PROVISIONER_SERVICE_TOKEN", "short-token")

    with pytest.raises(ValidationError, match="PROVISIONER_SERVICE_TOKEN"):
        IdentitySettings(_env_file=None)


def test_startup_rejects_placeholder_provisioner_token_when_host_set(
    monkeypatch,
):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "docker_provisioner:50052")
    monkeypatch.setenv("PROVISIONER_SERVICE_TOKEN", "changeme")

    with pytest.raises(ValidationError, match="placeholder"):
        IdentitySettings(_env_file=None)


def test_startup_strips_provisioner_token_when_host_set(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "docker_provisioner:50052")
    monkeypatch.setenv("PROVISIONER_SERVICE_TOKEN", f"  {'x' * 32}  ")

    settings = IdentitySettings(_env_file=None)

    assert settings.provisioner_service_token == "x" * 32


def test_startup_allows_empty_provisioner_token_when_host_unset(monkeypatch):
    _valid_env(monkeypatch)  # provisioner_grpc_host default ""
    settings = IdentitySettings(_env_file=None)
    assert settings.provisioner_service_token == ""


def test_docker_provisioner_client_uses_provisioner_service_token(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "provisioner:50052")
    monkeypatch.setenv("SERVICE_TOKEN", "s" * 40)
    monkeypatch.setenv("PROVISIONER_SERVICE_TOKEN", "p" * 40)

    from identity_api import dependencies

    captured: dict[str, object] = {}

    class RecordingClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        dependencies, "DockerProvisionerClient", RecordingClient
    )
    monkeypatch.setattr(
        dependencies, "settings", IdentitySettings(_env_file=None)
    )

    dependency = dependencies.get_docker_provisioner_client()
    try:
        client = next(dependency)
        assert isinstance(client, RecordingClient)
        assert captured["target"] == "provisioner:50052"
        assert captured["provisioner_service_token"] == "p" * 40
    finally:
        dependency.close()


def test_docker_provisioner_client_is_none_when_host_unset(monkeypatch):
    _valid_env(monkeypatch)

    from identity_api import dependencies

    monkeypatch.setattr(
        dependencies, "settings", IdentitySettings(_env_file=None)
    )

    assert list(dependencies.get_docker_provisioner_client()) == [None]
