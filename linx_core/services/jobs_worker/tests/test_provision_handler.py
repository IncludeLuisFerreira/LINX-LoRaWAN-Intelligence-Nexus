from uuid import uuid4

import grpc
import pytest
from linx_shared.clients.docker_provisioner import (
    ProvisionedApplication,
    ProvisionerClientError,
)
from linx_shared.jobs.constants import JOB_TYPE_PROVISION_APPLICATION
from linx_shared.jobs.handlers import PermanentJobError, TransientJobError
from linx_shared.models.job import Job

from jobs_worker.handlers.provision_application import (
    ProvisionApplicationHandler,
)


class FakeClient:
    def __init__(self, *, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.requests: list[str] = []
        self.closed = False

    def provision(self, app_id: str) -> ProvisionedApplication:
        self.requests.append(app_id)
        if self.error is not None:
            raise self.error
        return self.result

    def close(self) -> None:
        self.closed = True


def _job(subject_id=None) -> Job:
    return Job(
        type=JOB_TYPE_PROVISION_APPLICATION,
        tenant_id=uuid4(),
        subject_id=subject_id or uuid4(),
        payload={},
        command_exchange="linx.jobs",
        command_routing_key="provisioning.application.requested",
        deduplication_key=f"test:{uuid4()}",
    )


def _result() -> ProvisionedApplication:
    return ProvisionedApplication(
        container_id="container-1",
        port=8200,
        network="linx-app",
        image="linx-tenant-app:latest",
        status="running",
        created=True,
        mqtt_topic="application/x/device/+/event/up",
    )


def test_handler_returns_result_dict():
    client = FakeClient(result=_result())
    handler = ProvisionApplicationHandler(client_factory=lambda: client)

    result = handler.handle(_job())

    assert result == {
        "container_id": "container-1",
        "port": 8200,
        "network": "linx-app",
        "image": "linx-tenant-app:latest",
        "status": "running",
        "created": True,
        "mqtt_topic": "application/x/device/+/event/up",
    }
    assert client.closed is True


def test_handler_passes_subject_id_to_client():
    client = FakeClient(result=_result())
    subject_id = uuid4()
    handler = ProvisionApplicationHandler(client_factory=lambda: client)

    handler.handle(_job(subject_id))

    assert client.requests == [str(subject_id)]


def test_handler_maps_unavailable_to_transient():
    error = ProvisionerClientError(
        "unavailable",
        grpc_code=grpc.StatusCode.UNAVAILABLE,
    )
    client = FakeClient(error=error)
    handler = ProvisionApplicationHandler(client_factory=lambda: client)

    with pytest.raises(TransientJobError) as exc_info:
        handler.handle(_job())

    assert exc_info.value.grpc_code == "UNAVAILABLE"
    assert client.closed is True


def test_handler_maps_failed_precondition_to_permanent():
    error = ProvisionerClientError(
        "invalid",
        grpc_code=grpc.StatusCode.FAILED_PRECONDITION,
    )
    client = FakeClient(error=error)
    handler = ProvisionApplicationHandler(client_factory=lambda: client)

    with pytest.raises(PermanentJobError) as exc_info:
        handler.handle(_job())

    assert exc_info.value.grpc_code == "FAILED_PRECONDITION"
    assert client.closed is True
