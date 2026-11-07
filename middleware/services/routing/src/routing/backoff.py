"""Backoff exponencial com jitter para reconexões e retries."""

import random


def retry_delay(
    attempt: int, base_seconds: float, max_seconds: float
) -> float:
    """Retorna um atraso aleatório entre 0 e o teto exponencial da tentativa.

    ``attempt`` é 1-based. O teto dobra a cada tentativa e é limitado por
    ``max_seconds``; o jitter completo evita que vários clientes reconectem
    no mesmo instante.
    """
    if base_seconds <= 0:
        return 0.0
    ceiling = min(max_seconds, base_seconds * (2 ** (attempt - 1)))
    return random.uniform(0, ceiling)


def total_backoff_seconds(
    attempts: int, base_seconds: float, max_seconds: float
) -> float:
    """Soma dos tetos de backoff entre ``attempts`` tentativas."""
    if base_seconds <= 0:
        return 0.0
    return sum(
        min(max_seconds, base_seconds * (2 ** (attempt - 1)))
        for attempt in range(1, attempts)
    )
