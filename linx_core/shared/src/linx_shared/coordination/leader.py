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
        # ``None`` significa "ler o token do ServiceAccount a cada request":
        # o kubelet rotaciona o token projetado (~1h) e um valor cacheado no
        # startup passaria a receber 401 até o pod reiniciar.
        self._explicit_token = token
        self._ca_cert = ca_cert or self._default_ca_cert()
        self._timeout = timeout
        self._ssl_context: ssl.SSLContext | None = None

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

    def _lease_url(self, namespace: str, name: str | None = None) -> str:
        base = (
            f"{self._base_url}/apis/{LEASE_API_VERSION}/namespaces/"
            f"{namespace}/leases"
        )
        return base if name is None else f"{base}/{name}"

    def _context(self) -> ssl.SSLContext:
        if self._ssl_context is None:
            self._ssl_context = ssl.create_default_context(
                cafile=self._ca_cert
            )
        return self._ssl_context

    def _current_token(self) -> str:
        return self._explicit_token or self._default_token()

    def _request(
        self,
        method: str,
        namespace: str,
        name: str,
        body: dict[str, Any] | None,
        *,
        collection: bool = False,
    ) -> dict[str, Any] | None:
        # ``POST`` cria em ``.../leases`` (nome vai no body); ``GET``/``PUT``
        # usam ``.../leases/{name}``.
        url = self._lease_url(namespace, None if collection else name)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._current_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request, context=self._context(), timeout=self._timeout
            ) as response:
                raw = response.read().decode("utf-8")
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
            if exc.code in (401, 403):
                raise LeaderElectionError(
                    f"API de leases recusou a credencial (HTTP {exc.code}); "
                    "verifique o ServiceAccount e o Role/RoleBinding"
                ) from exc
            raise LeaderElectionError(
                f"API de leases respondeu HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise LeaderElectionError(
                f"falha ao acessar a API de leases: {exc}"
            ) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LeaderElectionError(
                "API de leases retornou JSON inválido"
            ) from exc

    def get(self, namespace: str, name: str) -> dict[str, Any] | None:
        return self._request("GET", namespace, name, None)

    def create(
        self, namespace: str, name: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        result = self._request("POST", namespace, name, body, collection=True)
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
        renew_deadline_seconds: int | None = None,
        retry_period_seconds: float = DEFAULT_RETRY_PERIOD_SECONDS,
        clock: Callable[[], datetime] | None = None,
        on_started_leading: Callable[[], None] | None = None,
        on_stopped_leading: Callable[[], None] | None = None,
    ) -> None:
        if lease_duration_seconds <= 0:
            raise ValueError("lease_duration_seconds deve ser maior que zero")
        if renew_deadline_seconds is None:
            # Renova até ~2/3 da duração: sobra ~1/3 para a API responder
            # antes de o Lease expirar para os demais candidatos.
            renew_deadline_seconds = max(1, (lease_duration_seconds * 2) // 3)
        if renew_deadline_seconds >= lease_duration_seconds:
            raise ValueError(
                "renew_deadline_seconds deve ser menor que "
                "lease_duration_seconds"
            )
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
        self._last_error: str | None = None

    def _now(self) -> datetime:
        return self._clock()

    def _now_iso(self) -> str:
        return self._now().isoformat(timespec="microseconds")

    @staticmethod
    def _lease_renew_time(lease: dict[str, Any]) -> datetime | None:
        value = lease.get("spec", {}).get("renewTime")
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _is_expired(self, lease: dict[str, Any]) -> bool:
        holder = lease.get("spec", {}).get("holderIdentity")
        if not holder:
            # Lease liberado explicitamente: qualquer réplica pode assumir.
            return True
        renew = self._lease_renew_time(lease)
        if renew is None:
            # Lease malformado/sem renewTime: trate como expirado para que
            # uma réplica saudável possa assumir.
            return True
        duration = lease.get("spec", {}).get("leaseDurationSeconds")
        if not isinstance(duration, int) or duration <= 0:
            duration = self._lease_duration_seconds
        return renew + timedelta(seconds=duration) <= self._now()

    def _lease_body(
        self,
        *,
        renew_time: str,
        acquire_time: str,
        resource_version: str | None = None,
        holder_identity: str | None = None,
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
                "holderIdentity": (
                    self._identity
                    if holder_identity is None
                    else holder_identity
                ),
                "leaseDurationSeconds": self._lease_duration_seconds,
                "acquireTime": acquire_time,
                "renewTime": renew_time,
            },
        }

    def _try_acquire(self) -> bool:
        try:
            lease = self._client.get(self._namespace, self._lease_name)
        except LeaderElectionError as exc:
            self._log_api_error("acquire", exc)
            return False
        now_iso = self._now_iso()
        if lease is None:
            try:
                self._client.create(
                    self._namespace,
                    self._lease_name,
                    self._lease_body(renew_time=now_iso, acquire_time=now_iso),
                )
                self._last_error = None
                return True
            except LeaderElectionError as exc:
                self._log_api_error("acquire", exc)
                return False
        holder = lease.get("spec", {}).get("holderIdentity")
        if holder == self._identity or self._is_expired(lease):
            # Em failover/takeover, ``acquireTime`` pertence ao titular
            # anterior; só preserve quando estamos renovando o nosso próprio
            # Lease.
            acquire_time = (
                (lease.get("spec", {}).get("acquireTime") or now_iso)
                if holder == self._identity
                else now_iso
            )
            try:
                self._client.replace(
                    self._namespace,
                    self._lease_name,
                    self._lease_body(
                        renew_time=now_iso,
                        acquire_time=acquire_time,
                        resource_version=lease.get("metadata", {}).get(
                            "resourceVersion"
                        ),
                    ),
                )
                self._last_error = None
                return True
            except LeaderElectionError as exc:
                self._log_api_error("acquire", exc)
                return False
        return False

    def _try_renew(self) -> datetime | None:
        lease = self._client.get(self._namespace, self._lease_name)
        if lease is None:
            return None
        holder = lease.get("spec", {}).get("holderIdentity")
        if holder != self._identity:
            return None
        # O deadline local deve contar a partir do instante *enviado* no
        # renewTime, não do retorno da API: uma resposta lenta não pode
        # manter a liderança local além da expiração vista pelos pares.
        now = self._now()
        try:
            self._client.replace(
                self._namespace,
                self._lease_name,
                self._lease_body(
                    renew_time=now.isoformat(timespec="microseconds"),
                    acquire_time=(
                        lease.get("spec", {}).get("acquireTime")
                        or now.isoformat(timespec="microseconds")
                    ),
                    resource_version=lease.get("metadata", {}).get(
                        "resourceVersion"
                    ),
                ),
            )
        except (LeaseConflictError, LeaseNotFoundError):
            return None
        self._last_error = None
        logger.debug("leader election: renewed")
        return now

    def run(self, stop_event: threading.Event) -> None:
        leading = False
        last_renewed: datetime | None = None
        try:
            while not stop_event.is_set():
                try:
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

                    stop_event.wait(self._retry_period_seconds)
                    if stop_event.is_set():
                        break
                    if last_renewed is not None and (
                        self._now() - last_renewed
                    ) >= timedelta(seconds=self._renew_deadline_seconds):
                        leading = False
                        self._notify_lost()
                        continue
                    renewed_at = self._try_renew()
                    if renewed_at is None:
                        leading = False
                        self._notify_lost()
                        continue
                    last_renewed = renewed_at
                except LeaderElectionError as exc:
                    # API temporariamente indisponível: continue tentando até
                    # o deadline local derrubar a liderança.
                    self._log_api_error("renew" if leading else "acquire", exc)
                    stop_event.wait(self._retry_period_seconds)
                except Exception:  # noqa: BLE001
                    logger.exception("leader election: erro inesperado")
                    if leading:
                        leading = False
                        self._notify_lost()
                    stop_event.wait(self._retry_period_seconds)
        finally:
            if leading:
                self._release()
                self._notify_lost()

    def _release(self) -> None:
        """Libera o Lease no shutdown para acelerar o failover."""
        try:
            lease = self._client.get(self._namespace, self._lease_name)
            if lease is None:
                return
            if lease.get("spec", {}).get("holderIdentity") != self._identity:
                return
            self._client.replace(
                self._namespace,
                self._lease_name,
                self._lease_body(
                    renew_time=self._now_iso(),
                    acquire_time=(
                        lease.get("spec", {}).get("acquireTime")
                        or self._now_iso()
                    ),
                    resource_version=lease.get("metadata", {}).get(
                        "resourceVersion"
                    ),
                    holder_identity="",
                ),
            )
            logger.info("leader election: released")
        except LeaderElectionError as exc:
            self._log_api_error("release", exc)
        except Exception:  # noqa: BLE001
            logger.exception("leader election: falha ao liberar o lease")

    def _log_api_error(self, operation: str, exc: LeaderElectionError) -> None:
        message = str(exc)
        if message != self._last_error:
            self._last_error = message
            logger.warning(
                "leader election: %s falhou: %s", operation, message
            )
        else:
            logger.debug("leader election: %s falhou: %s", operation, message)

    def _notify_lost(self) -> None:
        logger.info("leader election: lost")
        if self._on_stopped_leading is not None:
            self._on_stopped_leading()
