# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY linx_core/shared ./linx_core/shared
COPY middleware/services/routing ./middleware/services/routing

RUN poetry -C middleware/services/routing config virtualenvs.in-project true \
    && poetry -C middleware/services/routing install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/linx_core/shared ./linx_core/shared
COPY --from=builder /app/middleware/services/routing ./middleware/services/routing

ENV PATH="/app/middleware/services/routing/.venv/bin:$PATH" \
    PYTHONPATH=/app/middleware/services/routing/src:/app/linx_core/shared/src

RUN chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "routing.routing"]
