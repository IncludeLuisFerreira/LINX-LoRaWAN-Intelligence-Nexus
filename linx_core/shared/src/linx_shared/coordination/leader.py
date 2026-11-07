"""Eleição de líder via `coordination.k8s.io/v1 Lease`.

A eleição usa o mecanismo nativo do Kubernetes: cada réplica disputa um
``Lease`` no namespace do serviço; a que detém o ``Lease`` é a líder e a única
que executa os loops singleton (``outbox-relay`` e ``job-reaper`` no
``jobs_worker``).

Este módulo não depende da biblioteca ``kubernetes``: fala com a API via HTTP
in-cluster (``urllib`` da stdlib + token do ServiceAccount), o que mantém o
``linx_shared`` leve e torna o cliente trivial de simular nos testes.
"""

import json
import logging
import os
import ssl
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)

LEASE_API_VERSION = "coordination.k8s.io/v1"

DEFAULT_LEASE_DURATION_SECONDS = 15
DEFAULT_RENEW_DEADLINE_SECONDS = 10
DEFAULT_RETRY_PERIOD_SECONDS = 2.0

_SERVICE_ACCOUNT_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"


class LeaderElectionError(Exception):
    """Falha de comunicação com a API de leases do Kubernetes."""


class LeaseNotFoundError(LeaderElectionError):
    """Lease não encontrado (HTTP 404)."""


class LeaseConflictError(LeaderElectionError):
    """Conflito de versão (HTTP 409) — outro candidato atualizou o Lease."""


class LeaseClient(Protocol):
    """Contrato mínimo de acesso a um ``Lease``.

    Implementado por :class:`InClusterLeaseClient` em produção e por um fake
    nos testes.
    """

    def get(self, namespace: str, name: str) -> dict[str, Any] | None: ...

    def create(
        self, namespace: str, name: str, body: dict[str, Any]
    ) -> dict[str, Any]: ...

    def replace(
        self, namespace: str, name: str, body: dict[str, Any]
    ) -> dict[str, Any]: ...


def resolve_identity(env_identity: str | None = None) -> str:
    """Resolve a identidade do candidato.

    Precedência: ``LEADER_ELECTION_IDENTITY`` explícita → ``HOSTNAME`` (nome do
    pod no Kubernetes) → ``uuid4`` (fallback para ambientes sem Kubernetes).
    """
    identity = (env_identity or "").strip()
    if identity:
        return identity
    hostname = os.environ.get("HOSTNAME")
    if hostname:
        return hostname
    return str(uuid4())


def _read_serviceaccount_file(name: str) -> str:
    path = os.path.join(_SERVICE_ACCOUNT_DIR, name)
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


class InClusterLeaseClient:
    """Cliente HTTP in-cluster da API ``coordination.k8s.io/v1``.

    Os defaults leem o token/CA do ServiceAccount montado em
    ``/var/run/secrets/kubernetes.io/serviceaccount`` e o endereço do API
    server de ``KUBERNETES_SERVICE_HOST``/``KUBERNETES_SERVICE_PORT``.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        ca_cert: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = (base_url or self._default_base_url()).rstrip("/")
        self._token = token or self._default_token()
        self._ca_cert = ca_cert or self._default_ca_cert()
        self._timeout = timeout

    @staticmethod
    def _default_base_url() -> str:
        host = os.environ.get(
            "KUBERNETES_SERVICE_HOST", "kubernetes.default.svc"
        )
        port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
        return f"https://{host}:{port}"

    @staticmethod
    def _default_token() -> str:
        return _read_serviceaccount_file("token")

    @staticmethod
    def _default_ca_cert() -> str:
        return _read_serviceaccount_file("ca.crt")

    def _lease_url(self, namespace: str, name: str) -> str:
        return (
            f"{self._base_url}/apis/{LEASE_API_VERSION}/namespaces/"
            f"{namespace}/leases/{name}"
        )

    def _context(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=self._ca_cert)

    def _request(
        self,
        method: str,
        namespace: str,
        name: str,
        body: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        url = self._lease_url(namespace, name)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request, context=self._context(), timeout=self._timeout
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                raise LeaseConflictError(
                    f"lease {name!r} em {namespace!r} foi atualizado "
                    "concorrentemente"
                ) from exc
            if exc.code == 404:
                if method == "GET":
                    return None
                raise LeaseNotFoundError(
                    f"lease {name!r} em {namespace!r} não encontrado"
                ) from exc
            raise LeaderElectionError(
                f"API de leases respondeu HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise LeaderElectionError(
                f"falha ao acessar a API de leases: {exc}"
            ) from exc

    def get(self, namespace: str, name: str) -> dict[str, Any] | None:
        return self._request("GET", namespace, name, None)

    def create(
        self, namespace: str, name: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        result = self._request("POST", namespace, name, body)
        if result is None:  # inalcançável: 404 em POST vira exceção
            raise LeaderElectionError("create retornou resposta vazia")
        return result

    def replace(
        self, namespace: str, name: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        result = self._request("PUT", namespace, name, body)
        if result is None:  # inalcançável: 404 em PUT vira exceção
            raise LeaderElectionError("replace retornou resposta vazia")
        return result


class K8sLeaderElector:
    """Disputa um ``Lease`` do Kubernetes e sinaliza liderança.

    A réplica que detém o ``Lease`` (e consegue renová-lo) é a líder. As
    demais tentam adquirir quando o ``Lease`` expira. A liderança é exposta
    pelos callbacks ``on_started_leading``/``on_stopped_leading``; o parâmetro
    ``clock`` (injável) existe para testes determinísticos.
    """

    def __init__(
        self,
        *,
        client: LeaseClient,
        identity: str,
        namespace: str = "linx",
        lease_name: str = "jobs-worker",
        lease_duration_seconds: int = DEFAULT_LEASE_DURATION_SECONDS,
        renew_deadline_seconds: int = DEFAULT_RENEW_DEADLINE_SECONDS,
        retry_period_seconds: float = DEFAULT_RETRY_PERIOD_SECONDS,
        clock: Callable[[], datetime] | None = None,
        on_started_leading: Callable[[], None] | None = None,
        on_stopped_leading: Callable[[], None] | None = None,
    ) -> None:
        self._client = client
        self._identity = identity
        self._namespace = namespace
        self._lease_name = lease_name
        self._lease_duration_seconds = lease_duration_seconds
        self._renew_deadline_seconds = renew_deadline_seconds
        self._retry_period_seconds = retry_period_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._on_started_leading = on_started_leading
        self._on_stopped_leading = on_stopped_leading

    def _now(self) -> datetime:
        return self._clock()

    def _now_iso(self) -> str:
        return self._now().isoformat(timespec="microseconds")

    @staticmethod
    def _lease_renew_time(lease: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(lease["spec"]["renewTime"])

    def _is_expired(self, lease: dict[str, Any]) -> bool:
        renew = self._lease_renew_time(lease)
        limit = renew + timedelta(seconds=self._lease_duration_seconds)
        return limit <= self._now()

    def _lease_body(
        self,
        *,
        renew_time: str,
        acquire_time: str,
        resource_version: str | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "name": self._lease_name,
            "namespace": self._namespace,
        }
        if resource_version is not None:
            metadata["resourceVersion"] = resource_version
        return {
            "apiVersion": LEASE_API_VERSION,
            "kind": "Lease",
            "metadata": metadata,
            "spec": {
                "holderIdentity": self._identity,
                "leaseDurationSeconds": self._lease_duration_seconds,
                "acquireTime": acquire_time,
                "renewTime": renew_time,
            },
        }

    def _try_acquire(self) -> bool:
        lease = self._client.get(self._namespace, self._lease_name)
        now_iso = self._now_iso()
        if lease is None:
            try:
                self._client.create(
                    self._namespace,
                    self._lease_name,
                    self._lease_body(renew_time=now_iso, acquire_time=now_iso),
                )
                return True
            except LeaseConflictError:
                return False
        holder = lease.get("spec", {}).get("holderIdentity")
        if holder == self._identity or self._is_expired(lease):
            try:
                self._client.replace(
                    self._namespace,
                    self._lease_name,
                    self._lease_body(
                        renew_time=now_iso,
                        acquire_time=(
                            lease["spec"].get("acquireTime") or now_iso
                        ),
                        resource_version=lease["metadata"].get(
                            "resourceVersion"
                        ),
                    ),
                )
                return True
            except (LeaseConflictError, LeaseNotFoundError):
                return False
        return False

    def _try_renew(self) -> bool:
        lease = self._client.get(self._namespace, self._lease_name)
        if lease is None:
            return False
        holder = lease.get("spec", {}).get("holderIdentity")
        if holder != self._identity:
            return False
        try:
            self._client.replace(
                self._namespace,
                self._lease_name,
                self._lease_body(
                    renew_time=self._now_iso(),
                    acquire_time=(
                        lease["spec"].get("acquireTime") or self._now_iso()
                    ),
                    resource_version=lease["metadata"].get("resourceVersion"),
                ),
            )
            logger.info("leader election: renewed")
            return True
        except (LeaseConflictError, LeaseNotFoundError):
            return False

    def run(self, stop_event: threading.Event) -> None:
        leading = False
        last_renewed: datetime | None = None
        while not stop_event.is_set():
            if not leading:
                if self._try_acquire():
                    leading = True
                    last_renewed = self._now()
                    logger.info("leader election: acquired")
                    if self._on_started_leading is not None:
                        self._on_started_leading()
                else:
                    stop_event.wait(self._retry_period_seconds)
                continue

            while leading and not stop_event.is_set():
                stop_event.wait(self._retry_period_seconds)
                if stop_event.is_set():
                    break
                if last_renewed is not None and (
                    self._now() - last_renewed
                ) >= timedelta(seconds=self._renew_deadline_seconds):
                    leading = False
                    self._notify_lost()
                    break
                try:
                    renewed = self._try_renew()
                except LeaderElectionError:
                    # API temporariamente indisponível: o deadline acima
                    # derruba a liderança se ficarmos sem renovar.
                    logger.warning(
                        "leader election: falha ao renovar (API indisponível)"
                    )
                    continue
                if renewed:
                    last_renewed = self._now()
                else:
                    leading = False
                    self._notify_lost()
                    break

    def _notify_lost(self) -> None:
        logger.info("leader election: lost")
        if self._on_stopped_leading is not None:
            self._on_stopped_leading()
