from concurrent import futures
from unittest.mock import MagicMock

import docker
import grpc
import pytest
import requests
from linx_shared.grpc import (
    linx_docker_provisioner_pb2,
    linx_docker_provisioner_pb2_grpc,
)

from docker_provisioner import server as server_module
from docker_provisioner.config import settings
from docker_provisioner.server import (
    DockerProvisionerServicer,
    authorize,
    create_server,
    ensure_service_token,
)
from tests.fakes import FakeDockerClient

TOKEN = "test-service-token-0123456789abcdef"
AUTH_METADATA = [("authorization", f"Bearer {TOKEN}")]
APP_ID = "3d7f1a8e-3f4b-4f0a-9b7c-2e1d9a8b7c6d"


class AbortError(Exception):
    """Levantado pelo contexto fake quando context.abort é chamado."""


class FakeContext:
    def __init__(self, metadata=None) -> None:
        self.aborted: tuple[grpc.StatusCode, str] | None = None
        self._metadata = AUTH_METADATA if metadata is None else metadata

    def abort(self, code: grpc.StatusCode, details: str) -> None:
        self.aborted = (code, details)
        raise AbortError(details)

    def invocation_metadata(self):
        return self._metadata


@pytest.fixture(autouse=True)
def service_token(monkeypatch):
    monkeypatch.setattr(settings, "service_token", TOKEN)


@pytest.fixture(autouse=True)
def free_port(monkeypatch):
    """Evita bind real de portas do host nos testes de servidor."""
    monkeypatch.setattr(
        "docker_provisioner.docker_service._is_port_free",
        lambda *args, **kwargs: True,
    )


def _servicer(client: FakeDockerClient | None = None):
    fake = client or FakeDockerClient()
    return DockerProvisionerServicer(client_factory=lambda: fake), fake


def _request(app_id: str = APP_ID):
    request_cls = getattr(
        linx_docker_provisioner_pb2, "ProvisionApplicationRequest"
    )
    return request_cls(app_id=app_id)


def test_authorize_accepts_valid_bearer_token():
    authorize(FakeContext())


def test_authorize_rejects_missing_metadata():
    context = FakeContext(metadata=[])

    with pytest.raises(AbortError):
        authorize(context)

    assert context.aborted[0] == grpc.StatusCode.UNAUTHENTICATED


def test_authorize_rejects_wrong_token():
    context = FakeContext(
        metadata=[("authorization", "Bearer wrong-token-0123456789")]
    )

    with pytest.raises(AbortError):
        authorize(context)

    assert context.aborted[0] == grpc.StatusCode.UNAUTHENTICATED


def test_authorize_rejects_when_token_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "service_token", "")
    context = FakeContext()

    with pytest.raises(AbortError):
        authorize(context)

    assert context.aborted[0] == grpc.StatusCode.UNAUTHENTICATED


def test_ensure_service_token_rejects_blank(monkeypatch):
    monkeypatch.setattr(settings, "service_token", "   ")

    with pytest.raises(RuntimeError):
        ensure_service_token()


@pytest.mark.parametrize(
    "placeholder",
    ["changeme", "change-me-in-production"],
)
def test_ensure_service_token_rejects_placeholder(monkeypatch, placeholder):
    monkeypatch.setattr(settings, "service_token", placeholder)

    with pytest.raises(RuntimeError):
        ensure_service_token()


def test_ensure_service_token_rejects_short_token(monkeypatch):
    monkeypatch.setattr(settings, "service_token", "short")

    with pytest.raises(RuntimeError):
        ensure_service_token()


def test_ensure_service_token_accepts_strong_token():
    ensure_service_token()


def test_provision_application_rejects_invalid_uuid():
    servicer, _ = _servicer()
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.ProvisionApplication(_request("not-a-uuid"), context)

    assert context.aborted[0] == grpc.StatusCode.INVALID_ARGUMENT


def test_provision_application_returns_public_fields():
    servicer, client = _servicer()

    response = servicer.ProvisionApplication(_request(), FakeContext())

    assert response.container_id == "container-1"
    assert 8100 <= response.port <= 9100
    assert response.network == f"linx-app-{APP_ID}"
    assert response.image == settings.provision_image
    assert response.status == "running"
    assert response.created is True
    assert response.mqtt_topic == (f"application/{APP_ID}/device/+/event/up")
    env = client.containers.run_calls[0]["environment"]
    assert env["SERVICE_TOKEN"] == TOKEN
    assert "db_password" not in response.DESCRIPTOR.fields_by_name
    assert client.closed is True


def test_provision_application_maps_daemon_unavailable():
    client = FakeDockerClient()
    client.containers.list_error = docker.errors.DockerException("daemon down")
    servicer, _ = _servicer(client)
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.ProvisionApplication(_request(), context)

    assert context.aborted[0] == grpc.StatusCode.UNAVAILABLE


def test_provision_application_maps_connection_error_to_unavailable():
    client = FakeDockerClient()
    client.containers.list_error = requests.exceptions.ConnectionError(
        "daemon connection reset"
    )
    servicer, _ = _servicer(client)
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.ProvisionApplication(_request(), context)

    assert context.aborted[0] == grpc.StatusCode.UNAVAILABLE


def test_provision_application_maps_image_not_found():
    client = FakeDockerClient()
    client.containers.run_errors = [
        docker.errors.ImageNotFound("missing image")
    ]
    servicer, _ = _servicer(client)
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.ProvisionApplication(_request(), context)

    assert context.aborted[0] == grpc.StatusCode.FAILED_PRECONDITION


def test_create_server_binds_configured_address(monkeypatch):
    monkeypatch.setattr(settings, "grpc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "grpc_port", 0)

    server = create_server()
    try:
        assert isinstance(server, grpc.Server)
        server.start()
    finally:
        server.stop(0)


def test_create_server_raises_when_bind_fails(monkeypatch):
    fake_server = MagicMock()
    fake_server.add_insecure_port.return_value = 0
    monkeypatch.setattr(
        "docker_provisioner.server.grpc.server",
        lambda *args, **kwargs: fake_server,
    )
    monkeypatch.setattr(
        "docker_provisioner.server."
        "linx_docker_provisioner_pb2_grpc."
        "add_DockerProvisionerServicer_to_server",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(RuntimeError):
        create_server()


def test_serve_starts_and_waits_for_termination(monkeypatch):
    fake_server = MagicMock()
    monkeypatch.setattr(
        "docker_provisioner.server.create_server", lambda: fake_server
    )

    server_module.serve()

    fake_server.start.assert_called_once()
    fake_server.wait_for_termination.assert_called_once()


@pytest.fixture
def grpc_channel():
    servicer, _ = _servicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    linx_docker_provisioner_pb2_grpc.add_DockerProvisionerServicer_to_server(
        servicer, server
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield channel
    finally:
        channel.close()
        server.stop(0)


def test_provision_application_over_grpc(grpc_channel):
    stub = linx_docker_provisioner_pb2_grpc.DockerProvisionerStub(grpc_channel)

    response = stub.ProvisionApplication(_request(), metadata=AUTH_METADATA)

    assert response.container_id == "container-1"
    assert 8100 <= response.port <= 9100
    assert response.created is True


def test_provision_application_over_grpc_requires_auth(grpc_channel):
    stub = linx_docker_provisioner_pb2_grpc.DockerProvisionerStub(grpc_channel)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.ProvisionApplication(_request())

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_second_provision_over_grpc_is_idempotent(grpc_channel):
    stub = linx_docker_provisioner_pb2_grpc.DockerProvisionerStub(grpc_channel)

    first = stub.ProvisionApplication(_request(), metadata=AUTH_METADATA)
    second = stub.ProvisionApplication(_request(), metadata=AUTH_METADATA)

    assert second.container_id == first.container_id
    assert second.port == first.port
    assert second.created is False
