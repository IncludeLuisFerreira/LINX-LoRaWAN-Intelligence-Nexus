import pytest
from linx_shared.jobs.constants import PROVISIONING_STATUS_QUEUE
from pydantic import ValidationError

from jobs_status_worker.config import StatusWorkerSettings


def _valid_env(monkeypatch):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL",
        "amqp://linx:real-rabbit-pass@localhost:5672/",
    )


def test_defaults(monkeypatch):
    _valid_env(monkeypatch)

    settings = StatusWorkerSettings(_env_file=None)

    assert settings.status_queue == PROVISIONING_STATUS_QUEUE
    assert settings.status_queue == "linx.jobs.status"
    assert settings.status_concurrency == 2
    assert settings.status_prefetch == 4


def test_does_not_require_service_token_or_provisioner_host(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("PROVISIONER_GRPC_HOST", raising=False)

    settings = StatusWorkerSettings(_env_file=None)

    assert settings.service_token == ""


def test_rejects_missing_rabbitmq_url(monkeypatch):
    monkeypatch.delenv("RABBITMQ_AMQP_URL", raising=False)

    with pytest.raises(ValidationError, match="RABBITMQ_AMQP_URL"):
        StatusWorkerSettings(_env_file=None)


def test_rejects_guest_rabbitmq(monkeypatch):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL", "amqp://guest:guest@localhost:5672/"
    )

    with pytest.raises(ValidationError, match="guest:guest"):
        StatusWorkerSettings(_env_file=None)


def test_rejects_empty_status_queue(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("STATUS_QUEUE", "  ")

    with pytest.raises(ValidationError, match="STATUS_QUEUE"):
        StatusWorkerSettings(_env_file=None)


@pytest.mark.parametrize("var", ["STATUS_CONCURRENCY", "STATUS_PREFETCH"])
@pytest.mark.parametrize("value", ["0", "-1"])
def test_rejects_non_positive_ints(monkeypatch, var, value):
    _valid_env(monkeypatch)
    monkeypatch.setenv(var, value)

    with pytest.raises(ValidationError, match="maior que zero"):
        StatusWorkerSettings(_env_file=None)
