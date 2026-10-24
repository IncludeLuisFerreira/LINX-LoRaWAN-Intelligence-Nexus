# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

# Contexto de build é a raiz do repositório: o client_agent depende de
# linx-shared via path dependency (stubs gRPC do AgentBridge, #215).
COPY linx_core/shared ./linx_core/shared
COPY middleware/services/client_agent ./middleware/services/client_agent

RUN poetry -C middleware/services/client_agent config virtualenvs.in-project true \
    && poetry -C middleware/services/client_agent install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/linx_core/shared ./linx_core/shared
COPY --from=builder /app/middleware/services/client_agent ./middleware/services/client_agent

ENV PATH="/app/middleware/services/client_agent/.venv/bin:$PATH" \
    PYTHONPATH=/app/middleware/services/client_agent/src:/app/linx_core/shared/src

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8001"]
