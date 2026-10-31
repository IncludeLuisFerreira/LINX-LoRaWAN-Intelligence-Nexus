# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY shared ./shared
COPY services/docker_provisioner ./services/docker_provisioner

RUN poetry -C services/docker_provisioner config virtualenvs.in-project true \
    && poetry -C services/docker_provisioner install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/shared ./shared
COPY --from=builder /app/services/docker_provisioner ./services/docker_provisioner

ENV PATH="/app/services/docker_provisioner/.venv/bin:$PATH" \
    PYTHONPATH=/app/services/docker_provisioner/src:/app/shared/src

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 50052

CMD ["python", "-m", "docker_provisioner.server"]
