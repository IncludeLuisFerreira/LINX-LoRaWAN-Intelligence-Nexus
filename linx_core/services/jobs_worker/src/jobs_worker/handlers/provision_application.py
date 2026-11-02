import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

import grpc
from linx_shared.clients.docker_provisioner import (
    DockerProvisionerClient,
    ProvisionerClientError,
)
from linx_shared.jobs.constants import JOB_TYPE_PROVISION_APPLICATION
from linx_shared.jobs.handlers import PermanentJobError, TransientJobError
from linx_shared.models.application import Application
from linx_shared.models.job import Job
from sqlalchemy.orm import Session

from jobs_worker.config import settings

logger = logging.getLogger(__name__)

_TRANSIENT_GRPC_CODES = frozenset(
    {
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
    }
)


def _grpc_code_name(code: grpc.StatusCode | None) -> str | None:
    if code is None:
        return None
    return getattr(code, "name", str(code))


class ProvisionApplicationHandler:
    """Executa o provisionamento Docker de um job de aplicação."""

    job_type = JOB_TYPE_PROVISION_APPLICATION

    def __init__(
        self,
        client_factory: Callable[[], DockerProvisionerClient] | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._session_factory = session_factory

    def _create_client(self) -> DockerProvisionerClient:
        if self._client_factory is not None:
            return self._client_factory()
        return DockerProvisionerClient(
            target=settings.provisioner_grpc_host,
            service_token=settings.service_token,
            timeout=settings.provisioner_grpc_timeout_seconds,
        )

    def _application_exists(self, app_id: UUID) -> bool:
        """Confere se a aplicação ainda existe antes de provisionar.

        Fecha a janela TOCTOU entre o delete (que remove a linha) e um job de
        provisionamento enfileirado logo antes: sem a linha, provisionar
        criaria um container órfão com credenciais de um tenant removido.
        Sem ``session_factory`` (harness mínimo) o guard é ignorado.
        """
        if self._session_factory is None:
            return True
        session = self._session_factory()
        try:
            return session.get(Application, app_id) is not None
        finally:
            session.close()

    def handle(self, job: Job) -> dict[str, Any]:
        if not self._application_exists(job.subject_id):
            raise PermanentJobError(
                f"Application {job.subject_id} no longer exists; "
                "skipping provision",
                code="application_not_found",
            )
        client = self._create_client()
        try:
            result = client.provision(str(job.subject_id))
        except ProvisionerClientError as exc:
            grpc_code = _grpc_code_name(exc.grpc_code)
            if exc.grpc_code is None:
                logger.warning(
                    "provisioner client is misconfigured: %s",
                    exc.message,
                )
                raise TransientJobError(
                    exc.message,
                    code="provisioner_configuration_error",
                    grpc_code=grpc_code,
                ) from exc
            if exc.grpc_code in _TRANSIENT_GRPC_CODES:
                raise TransientJobError(
                    exc.message,
                    grpc_code=grpc_code,
                ) from exc
            raise PermanentJobError(
                exc.message,
                grpc_code=grpc_code,
            ) from exc
        finally:
            try:
                client.close()
            except Exception:
                logger.warning(
                    "failed to close provisioner client",
                    exc_info=True,
                )

        return {
            "container_id": result.container_id,
            "port": result.port,
            "network": result.network,
            "image": result.image,
            "status": result.status,
            "created": result.created,
            "mqtt_topic": result.mqtt_topic,
        }
