class ExternalServiceError(Exception):
    """Falha ao chamar um serviço externo (ex.: ChirpStack)."""

    def __init__(
        self,
        service: str,
        operation: str,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        self.service = service
        self.operation = operation
        self.message = message
        self.original_error = original_error
        super().__init__(f"{service}.{operation}: {message}")
