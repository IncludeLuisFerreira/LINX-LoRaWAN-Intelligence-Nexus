"""Política de falha de mensagens: ACK, retry limitado ou DLQ."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InvalidMessageError(Exception):
    """Mensagem inválida/venenosa: não deve voltar para a fila principal."""


class ProcessOutcome(StrEnum):
    ACK = "ack"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True)
class FailurePolicy:
    """Decide o destino de uma mensagem que falhou.

    ``max_attempts`` conta o total de tentativas de processamento (a primeira
    inclusa). Mensagem inválida nunca é reprocessada.
    """

    max_attempts: int = 3
    delays: tuple[float, ...] = (1.0, 2.0)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts deve ser >= 1")
        if any(delay < 0 for delay in self.delays):
            raise ValueError("delays não pode conter valor negativo")

    def decide(
        self,
        exc: BaseException,
        attempt: int,
    ) -> ProcessOutcome:
        if isinstance(exc, InvalidMessageError):
            return ProcessOutcome.DEAD_LETTER
        if attempt >= self.max_attempts:
            return ProcessOutcome.DEAD_LETTER
        return ProcessOutcome.RETRY

    def delay(self, attempt: int) -> float:
        if not self.delays:
            return 0.0
        index = min(max(attempt - 1, 0), len(self.delays) - 1)
        return self.delays[index]
