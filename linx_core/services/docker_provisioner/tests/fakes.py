"""Fakes de Docker usados pelos testes do provisioner.

A lógica de negócio recebe o client Docker por injeção de dependência. Estes
objetos reproduzem apenas o subconjunto da API do docker-py que o serviço
usa, mantendo os testes rápidos e independentes de um daemon real.
"""

from __future__ import annotations

import time
from typing import Any


class FakeContainer:
    """Container mínimo com os atributos consultados pelo provisioner."""

    def __init__(
        self,
        container_id: str,
        *,
        status: str = "running",
        labels: dict[str, str] | None = None,
        ports: dict[str, list[dict[str, str]]] | None = None,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.id = container_id
        self.status = status
        self.environment = environment or {}
        self.started = False
        self.removed = False
        self.remove_error: Exception | None = None
        self.attrs: dict[str, Any] = {
            "Id": container_id,
            "Config": {"Labels": labels or {}},
            "NetworkSettings": {"Ports": ports or {}},
            "State": {"Running": status == "running"},
        }

    def reload(self) -> None:
        self.attrs["State"]["Running"] = self.status == "running"

    def start(self) -> None:
        self.started = True
        self.status = "running"
        self.reload()

    def remove(self, *, force: bool = False) -> None:
        if self.remove_error is not None:
            raise self.remove_error
        self.removed = force
        self.status = "removed"


class FakeNetwork:
    def __init__(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.id = f"network-{name}"
        self.removed = False
        self.remove_error: Exception | None = None
        self.attrs: dict[str, Any] = {
            "Name": name,
            "Labels": labels or {},
            "Containers": {},
        }

    def remove(self) -> None:
        if self.remove_error is not None:
            raise self.remove_error
        self.removed = True


class FakeContainers:
    """Coleção de containers que simula list/run do docker-py."""

    def __init__(self) -> None:
        self.items: list[FakeContainer] = []
        self.run_calls: list[dict[str, Any]] = []
        self.list_error: Exception | None = None
        self.run_errors: list[Exception] = []
        self.run_delay = 0.0

    def list(self, all: bool = False, filters: dict[str, str] | None = None):
        if self.list_error is not None:
            raise self.list_error
        if not filters:
            return list(self.items)

        label = filters.get("label", "")
        if not label:
            return list(self.items)

        key, _, expected = label.partition("=")
        return [
            container
            for container in self.items
            if container.attrs["Config"]["Labels"].get(key) == expected
        ]

    def run(self, image: str, **kwargs: Any) -> FakeContainer:
        self.run_calls.append({"image": image, **kwargs})
        if self.run_delay:
            time.sleep(self.run_delay)
        if self.run_errors:
            raise self.run_errors.pop(0)

        labels = kwargs.get("labels", {})
        ports = kwargs.get("ports", {})
        published = {
            container_port: [
                {"HostIp": host_ip, "HostPort": str(host_port)}
                for host_ip, host_port in [mapping]
            ]
            for container_port, mapping in ports.items()
        }
        container = FakeContainer(
            f"container-{len(self.items) + 1}",
            labels=labels,
            ports=published,
            environment=kwargs.get("environment", {}),
        )
        self.items.append(container)
        return container


class FakeNetworks:
    """Rede fake com get/create idempotente."""

    def __init__(self) -> None:
        self.items: dict[str, FakeNetwork] = {}
        self.create_calls: list[dict[str, Any]] = []
        self.get_error: Exception | None = None
        self.create_error: Exception | None = None

    def get(self, name: str) -> FakeNetwork:
        if self.get_error is not None:
            raise self.get_error
        try:
            return self.items[name]
        except KeyError:
            import docker

            raise docker.errors.NotFound(f"network {name} not found")

    def create(self, name: str, **kwargs: Any) -> FakeNetwork:
        self.create_calls.append({"name": name, **kwargs})
        if self.create_error is not None:
            raise self.create_error
        network = FakeNetwork(name, labels=kwargs.get("labels"))
        self.items[name] = network
        return network


class FakeDockerClient:
    """Client Docker mínimo com containers e networks isolados por teste."""

    def __init__(self) -> None:
        self.containers = FakeContainers()
        self.networks = FakeNetworks()
        self.closed = False

    def close(self) -> None:
        self.closed = True
