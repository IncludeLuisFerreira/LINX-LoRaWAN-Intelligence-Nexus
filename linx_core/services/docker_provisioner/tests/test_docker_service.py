import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import docker
import grpc
import pytest

from docker_provisioner.docker_service import (
    ProvisioningError,
    allocate_port,
    provision_application,
)
from tests.fakes import FakeContainer, FakeDockerClient

APP_ID = "3d7f1a8e-3f4b-4f0a-9b7c-2e1d9a8b7c6d"


class FakeSocket:
    """Socket que falha no bind quando a porta está ocupada no host."""

    def __init__(self, used_ports: set[int]) -> None:
        self.used_ports = used_ports

    def bind(self, address: tuple[str, int]) -> None:
        if address[1] in self.used_ports:
            raise OSError("address already in use")

    def close(self) -> None:
        return None


def _patch_socket(used_ports: set[int] | None = None):
    used = used_ports or set()
    return patch(
        "docker_provisioner.docker_service.socket.socket",
        side_effect=lambda *args, **kwargs: FakeSocket(used),
    )


def _add_published_port(
    client: FakeDockerClient, port: int, *, status: str = "running"
) -> FakeContainer:
    container = FakeContainer(
        f"existing-{port}",
        status=status,
        ports={"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(port)}]},
    )
    client.containers.items.append(container)
    return container


def _provision(client: FakeDockerClient, *, app_id: str = APP_ID, **overrides):
    params: dict[str, Any] = {
        "image": "linx-tenant-app:latest",
        "port_min": 8100,
        "port_max": 9100,
        "bind_host": "0.0.0.0",
        "network_prefix": "linx-app",
        "container_port": 8000,
        "service_token": "test-service-token-0123456789abcdef",
    }
    params.update(overrides)
    return provision_application(client, app_id, **params)


def test_allocate_port_returns_port_in_range():
    client = FakeDockerClient()

    with _patch_socket():
        port = allocate_port(
            client, 8100, 9100, "0.0.0.0", rng=random.Random(1)
        )

    assert 8100 <= port <= 9100


def test_allocate_port_skips_docker_published_ports():
    client = FakeDockerClient()
    _add_published_port(client, 8100)

    with _patch_socket():
        port = allocate_port(
            client, 8100, 9100, "0.0.0.0", rng=random.Random(1)
        )

    assert port != 8100
    assert 8100 <= port <= 9100


def test_allocate_port_skips_host_bound_ports():
    client = FakeDockerClient()

    with _patch_socket({8100}):
        port = allocate_port(
            client, 8100, 9100, "0.0.0.0", rng=random.Random(1)
        )

    assert port != 8100


def test_allocate_port_raises_resource_exhausted():
    client = FakeDockerClient()

    with _patch_socket({8100, 8101}):
        with pytest.raises(ProvisioningError) as exc_info:
            allocate_port(client, 8100, 8101, "0.0.0.0", rng=random.Random(1))

    assert exc_info.value.status == grpc.StatusCode.RESOURCE_EXHAUSTED


def test_provision_creates_network_and_container_with_env_and_labels():
    client = FakeDockerClient()
    container_port = 8000

    with _patch_socket():
        result = _provision(client)

    assert result.created is True
    assert result.container_id == "container-1"
    assert result.image == "linx-tenant-app:latest"
    assert result.network == f"linx-app-{APP_ID}"
    assert result.status == "running"
    assert result.mqtt_topic == f"application/{APP_ID}/device/+/event/up"
    assert 8100 <= result.port <= 9100

    assert len(client.networks.create_calls) == 1
    assert client.networks.create_calls[0]["name"] == f"linx-app-{APP_ID}"
    assert client.networks.create_calls[0]["driver"] == "bridge"

    assert len(client.containers.run_calls) == 1
    call = client.containers.run_calls[0]
    assert call["image"] == "linx-tenant-app:latest"
    assert call["name"] == f"linx-app-{APP_ID}"
    assert call["detach"] is True
    assert call["network"] == f"linx-app-{APP_ID}"
    assert call["ports"] == {f"{container_port}/tcp": ("0.0.0.0", result.port)}
    assert call["labels"] == {
        "linx.managed-by": "linx-core",
        "linx.application.id": APP_ID,
    }
    assert call["restart_policy"] == {"Name": "unless-stopped"}
    assert call["security_opt"] == ["no-new-privileges:true"]
    assert call["environment"]["APP_ID"] == APP_ID
    assert call["environment"]["SERVICE_TOKEN"] == (
        "test-service-token-0123456789abcdef"
    )
    assert call["environment"]["MQTT_TOPIC"] == (
        f"application/{APP_ID}/device/+/event/up"
    )
    assert call["environment"]["DB_PASSWORD"]
    assert "db_password" not in result.__dict__


def test_provision_reuses_existing_network():
    client = FakeDockerClient()
    client.networks.items[f"linx-app-{APP_ID}"] = type(
        "Network", (), {"name": f"linx-app-{APP_ID}"}
    )()

    with _patch_socket():
        _provision(client)

    assert client.networks.create_calls == []
    assert len(client.containers.run_calls) == 1


def test_provision_is_idempotent_for_existing_container():
    client = FakeDockerClient()
    existing = FakeContainer(
        "existing-container",
        labels={"linx.application.id": APP_ID},
        ports={"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8200"}]},
    )
    client.containers.items.append(existing)

    result = _provision(client)

    assert result.created is False
    assert result.container_id == "existing-container"
    assert result.port == 8200
    assert result.status == "running"
    assert client.containers.run_calls == []


def test_provision_reports_actual_image_and_network_of_existing_container():
    client = FakeDockerClient()
    existing = FakeContainer(
        "existing-container",
        labels={"linx.application.id": APP_ID},
        ports={"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8200"}]},
    )
    existing.attrs["Config"]["Image"] = "actual-image:1.2.3"
    existing.attrs["NetworkSettings"]["Networks"] = {"actual-network": {}}
    client.containers.items.append(existing)

    result = _provision(client)

    assert result.image == "actual-image:1.2.3"
    assert result.network == "actual-network"


def test_provision_starts_stopped_container():
    client = FakeDockerClient()
    existing = FakeContainer(
        "stopped-container",
        status="exited",
        labels={"linx.application.id": APP_ID},
        ports={"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8200"}]},
    )
    client.containers.items.append(existing)

    result = _provision(client)

    assert existing.started is True
    assert result.created is False
    assert result.status == "running"


def test_provision_rejects_multiple_containers():
    client = FakeDockerClient()
    for index in range(2):
        client.containers.items.append(
            FakeContainer(
                f"duplicate-{index}",
                labels={"linx.application.id": APP_ID},
                ports={
                    "8000/tcp": [
                        {"HostIp": "0.0.0.0", "HostPort": str(8200 + index)}
                    ]
                },
            )
        )

    with pytest.raises(ProvisioningError) as exc_info:
        _provision(client)

    assert exc_info.value.status == grpc.StatusCode.ABORTED


def test_provision_image_not_found_maps_failed_precondition():
    client = FakeDockerClient()
    client.containers.run_errors = [
        docker.errors.ImageNotFound("image not found")
    ]

    with _patch_socket(), pytest.raises(ProvisioningError) as exc_info:
        _provision(client)

    assert exc_info.value.status == grpc.StatusCode.FAILED_PRECONDITION


def test_provision_daemon_unavailable_maps_unavailable():
    client = FakeDockerClient()
    client.containers.list_error = docker.errors.DockerException(
        "daemon unavailable"
    )

    with _patch_socket(), pytest.raises(ProvisioningError) as exc_info:
        _provision(client)

    assert exc_info.value.status == grpc.StatusCode.UNAVAILABLE


def test_provision_api_error_maps_internal():
    client = FakeDockerClient()
    client.containers.run_errors = [docker.errors.APIError("boom")]

    with _patch_socket(), pytest.raises(ProvisioningError) as exc_info:
        _provision(client)

    assert exc_info.value.status == grpc.StatusCode.INTERNAL


def test_provision_retries_on_port_collision():
    client = FakeDockerClient()
    client.containers.run_errors = [
        docker.errors.APIError("409 port is already allocated")
    ]

    with _patch_socket():
        result = _provision(client)

    assert result.created is True
    assert len(client.containers.run_calls) == 2
    first_port = client.containers.run_calls[0]["ports"]["8000/tcp"][1]
    second_port = client.containers.run_calls[1]["ports"]["8000/tcp"][1]
    assert first_port != second_port


def test_provision_uses_uuid_app_id_from_request():
    client = FakeDockerClient()
    app_id = str(uuid4())

    with _patch_socket():
        result = _provision(client, app_id=app_id)

    assert result.mqtt_topic == f"application/{app_id}/device/+/event/up"


def test_provision_serializes_concurrent_calls_for_same_app():
    client = FakeDockerClient()
    client.containers.run_delay = 0.05

    with _patch_socket(), ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _provision(client), range(2)))

    assert len(client.containers.items) == 1
    assert sorted(result.created for result in results) == [False, True]
    assert len({result.container_id for result in results}) == 1
