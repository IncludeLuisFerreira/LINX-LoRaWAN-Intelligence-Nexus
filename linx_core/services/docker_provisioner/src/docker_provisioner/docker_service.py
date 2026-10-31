from __future__ import annotations

import random
import secrets
import socket
import threading
from dataclasses import dataclass
from typing import Any

import docker
import grpc

MANAGED_LABEL = "linx.managed-by"
APP_LABEL = "linx.application.id"
MANAGED_BY = "linx-core"

PORT_COLLISION_FRAGMENTS = (
    "port is already allocated",
    "address already in use",
)
MAX_PORT_ATTEMPTS = 5

# Locks por aplicação: duas chamadas concorrentes para o mesmo app não podem
# passar juntas pelo check-then-act e tentar criar dois containers com o mesmo
# nome. O servidor gRPC atende em múltiplas threads, então a serialização é
# necessária mesmo com uma única instância do processo.
_APP_LOCKS: dict[str, threading.Lock] = {}
_APP_LOCKS_GUARD = threading.Lock()


class ProvisioningError(RuntimeError):
    """Erro de provisionamento já traduzido para um status gRPC."""

    def __init__(
        self,
        message: str,
        *,
        status: grpc.StatusCode = grpc.StatusCode.INTERNAL,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(frozen=True)
class ProvisionResult:
    """Dados públicos devolvidos ao identity_api."""

    container_id: str
    port: int
    network: str
    image: str
    status: str
    created: bool
    mqtt_topic: str


def mqtt_topic_for(app_id: str) -> str:
    """Tópico MQTT de uplink consumido pelo tenant."""
    return f"application/{app_id}/device/+/event/up"


def _published_host_ports(client: docker.DockerClient) -> set[int]:
    """Coleta portas do host publicadas por qualquer container gerenciado.

    Considera containers parados também: eles mantêm a alocação de porta no
    Docker até serem removidos e podem voltar a rodar.
    """
    try:
        containers = client.containers.list(all=True)
    except docker.errors.DockerException as exc:
        raise ProvisioningError(
            f"Docker daemon indisponível: {exc}",
            status=grpc.StatusCode.UNAVAILABLE,
        ) from exc

    used: set[int] = set()
    for container in containers:
        ports = container.attrs.get("NetworkSettings", {}).get("Ports") or {}
        for mappings in ports.values():
            for mapping in mappings or []:
                host_port = mapping.get("HostPort")
                if host_port:
                    used.add(int(host_port))
    return used


def _is_port_free(port: int, bind_host: str) -> bool:
    """Testa bind local antes de pedir a publicação ao Docker.

    No modo host, detecta processos que não aparecem na API do Docker. Dentro
    do container do provisioner, o bind ocorre no namespace do próprio
    container; nesse caso a garantia final é o retry quando o Docker rejeita
    a porta já alocada.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((bind_host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def allocate_port(
    client: docker.DockerClient,
    port_min: int,
    port_max: int,
    bind_host: str,
    *,
    rng: random.Random | None = None,
    exclude_ports: set[int] | None = None,
) -> int:
    """Sorteia uma porta livre no range configurado.

    Usa `secrets.SystemRandom` em produção (CSPRNG) e permite injetar um
    `random.Random` semeado nos testes. Portas já publicadas no Docker, já
    tentadas nesta chamada e indisponíveis no bind do host são descartadas.
    """
    if port_min > port_max:
        raise ValueError("port_min não pode ser maior que port_max")

    used = _published_host_ports(client)
    excluded = exclude_ports or set()
    candidates = list(range(port_min, port_max + 1))
    (rng or secrets.SystemRandom()).shuffle(candidates)

    for port in candidates:
        if port in used or port in excluded:
            continue
        if _is_port_free(port, bind_host):
            return port

    raise ProvisioningError(
        f"Nenhuma porta livre no range {port_min}-{port_max}",
        status=grpc.StatusCode.RESOURCE_EXHAUSTED,
    )


def ensure_network(
    client: docker.DockerClient,
    app_id: str,
    prefix: str,
) -> Any:
    """Cria ou reutiliza a rede bridge dedicada da aplicação."""
    name = f"{prefix}-{app_id}"
    labels = {
        MANAGED_LABEL: MANAGED_BY,
        APP_LABEL: app_id,
    }

    try:
        return client.networks.get(name)
    except docker.errors.NotFound:
        pass
    except docker.errors.DockerException as exc:
        raise ProvisioningError(
            f"Falha ao consultar rede {name}: {exc}",
            status=grpc.StatusCode.UNAVAILABLE,
        ) from exc

    try:
        return client.networks.create(
            name,
            driver="bridge",
            labels=labels,
        )
    except docker.errors.APIError as exc:
        raise ProvisioningError(
            f"Falha ao criar rede {name}: {exc}",
            status=grpc.StatusCode.INTERNAL,
        ) from exc


def _find_containers(client: docker.DockerClient, app_id: str) -> list[Any]:
    try:
        return client.containers.list(
            all=True,
            filters={"label": f"{APP_LABEL}={app_id}"},
        )
    except docker.errors.DockerException as exc:
        raise ProvisioningError(
            f"Docker daemon indisponível: {exc}",
            status=grpc.StatusCode.UNAVAILABLE,
        ) from exc


def _published_port(container: Any, container_port: int) -> int:
    ports = container.attrs.get("NetworkSettings", {}).get("Ports") or {}
    mappings = ports.get(f"{container_port}/tcp") or []
    if not mappings:
        raise ProvisioningError(
            "Container existente não possui porta publicada",
            status=grpc.StatusCode.INTERNAL,
        )
    return int(mappings[0]["HostPort"])


def _result_from_existing(
    container: Any,
    *,
    container_port: int,
    network: str,
    image: str,
    app_id: str,
) -> ProvisionResult:
    if container.status != "running":
        try:
            container.start()
        except docker.errors.DockerException as exc:
            raise ProvisioningError(
                f"Falha ao iniciar container existente: {exc}",
                status=grpc.StatusCode.INTERNAL,
            ) from exc
        container.reload()

    # Reflete o container real: configuração pode ter mudado desde a criação.
    actual_image = container.attrs.get("Config", {}).get("Image") or image
    networks = container.attrs.get("NetworkSettings", {}).get("Networks") or {}
    actual_network = next(iter(networks), network)

    return ProvisionResult(
        container_id=container.id,
        port=_published_port(container, container_port),
        network=actual_network,
        image=actual_image,
        status=container.status,
        created=False,
        mqtt_topic=mqtt_topic_for(app_id),
    )


def _is_port_collision(exc: docker.errors.APIError) -> bool:
    message = str(exc).lower()
    return any(fragment in message for fragment in PORT_COLLISION_FRAGMENTS)


def _app_lock(app_id: str) -> threading.Lock:
    """Retorna o lock exclusivo da aplicação, criando-o sob demanda."""
    with _APP_LOCKS_GUARD:
        return _APP_LOCKS.setdefault(app_id, threading.Lock())


def provision_application(
    client: docker.DockerClient,
    app_id: str,
    *,
    image: str,
    port_min: int,
    port_max: int,
    bind_host: str,
    network_prefix: str,
    container_port: int,
    service_token: str,
) -> ProvisionResult:
    """Provisiona (ou reaproveita) o container Docker de uma aplicação.

    A operação é serializada por `app_id` e idempotente por label: se já
    existir container, ele é iniciado (se necessário) e os mesmos dados são
    retornados. O `DB_PASSWORD` é gerado aqui e nunca entra no resultado
    público.
    """
    with _app_lock(app_id):
        return _provision_application_locked(
            client,
            app_id,
            image=image,
            port_min=port_min,
            port_max=port_max,
            bind_host=bind_host,
            network_prefix=network_prefix,
            container_port=container_port,
            service_token=service_token,
        )


def _provision_application_locked(
    client: docker.DockerClient,
    app_id: str,
    *,
    image: str,
    port_min: int,
    port_max: int,
    bind_host: str,
    network_prefix: str,
    container_port: int,
    service_token: str,
) -> ProvisionResult:
    existing = _find_containers(client, app_id)
    if len(existing) > 1:
        raise ProvisioningError(
            f"Múltiplos containers encontrados para {app_id}",
            status=grpc.StatusCode.ABORTED,
        )
    if existing:
        return _result_from_existing(
            existing[0],
            container_port=container_port,
            network=f"{network_prefix}-{app_id}",
            image=image,
            app_id=app_id,
        )

    network = ensure_network(client, app_id, network_prefix)
    environment = {
        "APP_ID": app_id,
        "DB_PASSWORD": secrets.token_urlsafe(16),
        "MQTT_TOPIC": mqtt_topic_for(app_id),
        "SERVICE_TOKEN": service_token,
    }
    labels = {
        MANAGED_LABEL: MANAGED_BY,
        APP_LABEL: app_id,
    }

    tried_ports: set[int] = set()
    for _ in range(MAX_PORT_ATTEMPTS):
        port = allocate_port(
            client,
            port_min,
            port_max,
            bind_host,
            exclude_ports=tried_ports,
        )
        tried_ports.add(port)

        try:
            container = client.containers.run(
                image,
                detach=True,
                name=f"{network_prefix}-{app_id}",
                ports={f"{container_port}/tcp": (bind_host, port)},
                environment=environment,
                network=network.name,
                labels=labels,
                restart_policy={"Name": "unless-stopped"},
                security_opt=["no-new-privileges:true"],
            )
        except docker.errors.ImageNotFound as exc:
            raise ProvisioningError(
                f"Imagem {image} não encontrada: {exc}",
                status=grpc.StatusCode.FAILED_PRECONDITION,
            ) from exc
        except docker.errors.APIError as exc:
            # Outro processo pode ter ocupado a porta entre o bind check e o
            # run; nesse caso vale tentar a próxima porta.
            if _is_port_collision(exc):
                continue
            raise ProvisioningError(
                f"Falha ao criar container: {exc}",
                status=grpc.StatusCode.INTERNAL,
            ) from exc
        except docker.errors.DockerException as exc:
            raise ProvisioningError(
                f"Docker daemon indisponível: {exc}",
                status=grpc.StatusCode.UNAVAILABLE,
            ) from exc

        # `run(detach=True)` retorna assim que o container é iniciado; um
        # reload garante que o status devolvido reflita o estado real.
        container.reload()

        return ProvisionResult(
            container_id=container.id,
            port=port,
            network=network.name,
            image=image,
            status=container.status,
            created=True,
            mqtt_topic=mqtt_topic_for(app_id),
        )

    raise ProvisioningError(
        "Não foi possível alocar uma porta após várias tentativas",
        status=grpc.StatusCode.RESOURCE_EXHAUSTED,
    )
