# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY shared ./shared
COPY routing ./routing

RUN poetry -C routing config virtualenvs.in-project true \
    && poetry -C routing install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/shared ./shared
COPY --from=builder /app/routing ./routing

ENV PATH="/app/routing/.venv/bin:$PATH" \
    PYTHONPATH=/app/routing/src:/app/shared/src

RUN chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "routing.routing"]
