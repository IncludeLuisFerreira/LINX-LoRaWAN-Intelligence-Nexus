# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY shared ./shared
COPY agent_bridge ./agent_bridge

RUN poetry -C agent_bridge config virtualenvs.in-project true \
    && poetry -C agent_bridge install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/shared ./shared
COPY --from=builder /app/agent_bridge ./agent_bridge

ENV PATH="/app/agent_bridge/.venv/bin:$PATH" \
    PYTHONPATH=/app/agent_bridge/src:/app/shared/src

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 50051

CMD ["python", "-m", "agent_bridge.server"]
