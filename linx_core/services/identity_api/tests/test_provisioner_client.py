from concurrent import futures
from contextlib import contextmanager

import grpc
import pytest
from linx_shared.grpc import (
    linx_docker_provisioner_pb2,
    linx_docker_provisioner_pb2_grpc,
)

from identity_api.provisioner_client import (
    DockerProvisionerClient,
    ProvisionerClientError,
)

TOKEN = "test-service-token-0123456789abcdef"
APP_ID = "3d7f1a8e-3f4b-4f0a-9b7c-2e1d9a8b7c6d"
RESPONSE_CLS = getattr(
    linx_docker_provisioner_pb2, "ProvisionApplicationResponse"
)


class FakeProvisionerServicer(
    linx_docker_provisioner_pb2_grpc.DockerProvisionerServicer
):
    def __init__(self, *, error_code=None) -> None:
        self.error_code = error_code
        self.requests: list[str] = []
        self.metadata: list[tuple[str, str]] = []

    def ProvisionApplication(self, request, context):
        self.requests.append(request.app_id)
        self.metadata = list(context.invocation_metadata())
        if self.error_code is not None:
            context.abort(self.error_code, "boom")

        return RESPONSE_CLS(
            container_id="container-1",
            port=8200,
            network=f"linx-app-{request.app_id}",
            image="linx-tenant-app:latest",
            status="running",
            created=True,
            mqtt_topic=f"application/{request.app_id}/device/+/event/up",
        )


@contextmanager
def _serve(servicer):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    linx_docker_provisioner_pb2_grpc.add_DockerProvisionerServicer_to_server(
        servicer, server
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield f"127.0.0.1:{port}"
    finally:
        server.stop(0)


def _client(target: str, *, service_token: str = TOKEN):
    return DockerProvisionerClient(
        target=target,
        service_token=service_token,
        timeout=2.0,
    )


def test_provision_sends_app_id_and_bearer_token():
    servicer = FakeProvisionerServicer()

    with _serve(servicer) as target:
        client = _client(target)
        try:
            result = client.provision(APP_ID)
        finally:
            client.close()

    assert servicer.requests == [APP_ID]
    assert ("authorization", f"Bearer {TOKEN}") in servicer.metadata
    assert result.container_id == "container-1"
    assert result.port == 8200
    assert result.network == f"linx-app-{APP_ID}"
    assert result.image == "linx-tenant-app:latest"
    assert result.status == "running"
    assert result.created is True
    assert result.mqtt_topic == (f"application/{APP_ID}/device/+/event/up")


@pytest.mark.parametrize(
    ("grpc_code", "http_status"),
    [
        (grpc.StatusCode.UNAVAILABLE, 503),
        (grpc.StatusCode.DEADLINE_EXCEEDED, 504),
        (grpc.StatusCode.RESOURCE_EXHAUSTED, 503),
        (grpc.StatusCode.ABORTED, 409),
        (grpc.StatusCode.UNAUTHENTICATED, 502),
        (grpc.StatusCode.PERMISSION_DENIED, 502),
        (grpc.StatusCode.INVALID_ARGUMENT, 502),
        (grpc.StatusCode.FAILED_PRECONDITION, 502),
        (grpc.StatusCode.INTERNAL, 502),
        (grpc.StatusCode.UNKNOWN, 502),
    ],
)
def test_provision_maps_grpc_errors(grpc_code, http_status):
    servicer = FakeProvisionerServicer(error_code=grpc_code)

    with _serve(servicer) as target:
        client = _client(target)
        try:
            with pytest.raises(ProvisionerClientError) as exc_info:
                client.provision(APP_ID)
        finally:
            client.close()

    assert exc_info.value.status_code == http_status


def test_provision_fails_closed_without_service_token():
    client = DockerProvisionerClient(
        target="127.0.0.1:1",
        service_token="",
        timeout=0.1,
    )
    try:
        with pytest.raises(ProvisionerClientError) as exc_info:
            client.provision(APP_ID)
    finally:
        client.close()

    assert exc_info.value.status_code == 503
