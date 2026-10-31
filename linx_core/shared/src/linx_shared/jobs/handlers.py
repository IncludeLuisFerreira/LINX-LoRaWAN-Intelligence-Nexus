from typing import Any, Protocol

from linx_shared.models.job import Job


class TransientJobError(Exception):
    """Falha temporária: o job pode ser reexecutado."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "transient_error",
        grpc_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.grpc_code = grpc_code


class PermanentJobError(Exception):
    """Falha definitiva: o job não deve ser reexecutado."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "permanent_error",
        grpc_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.grpc_code = grpc_code


class JobHandler(Protocol):
    job_type: str

    def handle(self, job: Job) -> dict[str, Any]: ...


class HandlerRegistry:
    """Registro de handlers indexado pelo tipo do job."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, handler: JobHandler) -> None:
        self._handlers[handler.job_type] = handler

    def get(self, job_type: str) -> JobHandler:
        return self._handlers[job_type]
