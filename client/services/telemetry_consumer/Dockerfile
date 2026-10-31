# --- STAGE 1: Builder ---
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY pyproject.toml poetry.lock ./
COPY src ./src

RUN poetry config virtualenvs.in-project true \
    && poetry install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "telemetry_consumer.app:app", "--host", "0.0.0.0", "--port", "8000"]
