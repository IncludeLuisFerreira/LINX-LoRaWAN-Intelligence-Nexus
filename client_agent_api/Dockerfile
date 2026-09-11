# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
COPY src ./src

RUN poetry config virtualenvs.in-project true \
    && poetry install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src

ENV PATH="/app/.venv/bin:$PATH"

USER appuser

EXPOSE 8000

CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
