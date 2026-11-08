import pytest
from pydantic import ValidationError

from jobs_worker.config import WorkerSettings


def _valid_env(monkeypatch):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL",
        "amqp://linx:real-rabbit-pass@localhost:5672/",
    )
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token-0123456789abcdef")
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", "127.0.0.1:50052")


def test_startup_accepts_full_config(monkeypatch):
    _valid_env(monkeypatch)

    settings = WorkerSettings(_env_file=None)

    assert settings.service_token == "test-service-token-0123456789abcdef"
    assert settings.provisioner_grpc_host == "127.0.0.1:50052"
    assert settings.worker_prefetch == 4
    assert not hasattr(settings, "job_max_attempts")


def test_startup_rejects_missing_service_token(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)

    with pytest.raises(ValidationError, match="SERVICE_TOKEN"):
        WorkerSettings(_env_file=None)


def test_startup_rejects_placeholder_service_token(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("SERVICE_TOKEN", "changeme")

    with pytest.raises(ValidationError, match="SERVICE_TOKEN"):
        WorkerSettings(_env_file=None)


def test_startup_rejects_empty_provisioner_host(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("PROVISIONER_GRPC_HOST", " ")

    with pytest.raises(ValidationError, match="PROVISIONER_GRPC_HOST"):
        WorkerSettings(_env_file=None)


def test_leader_election_defaults_disabled(monkeypatch):
    _valid_env(monkeypatch)

    settings = WorkerSettings(_env_file=None)

    assert settings.leader_election_enabled is False
    assert settings.leader_election_lease_name == "jobs-worker"
    assert settings.leader_election_namespace == "linx"
    assert settings.leader_election_identity == ""
    assert settings.leader_election_lease_duration_seconds == 15


def test_leader_election_env(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("LEADER_ELECTION_ENABLED", "true")
    monkeypatch.setenv("LEADER_ELECTION_LEASE_NAME", "my-lease")
    monkeypatch.setenv("LEADER_ELECTION_NAMESPACE", "prod")
    monkeypatch.setenv("LEADER_ELECTION_IDENTITY", "pod-7")
    monkeypatch.setenv("LEADER_ELECTION_LEASE_DURATION_SECONDS", "30")

    settings = WorkerSettings(_env_file=None)

    assert settings.leader_election_enabled is True
    assert settings.leader_election_lease_name == "my-lease"
    assert settings.leader_election_namespace == "prod"
    assert settings.leader_election_identity == "pod-7"
    assert settings.leader_election_lease_duration_seconds == 30
