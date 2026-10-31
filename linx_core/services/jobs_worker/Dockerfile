# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY shared ./shared
COPY services/jobs_worker ./services/jobs_worker

RUN poetry -C services/jobs_worker config virtualenvs.in-project true \
    && poetry -C services/jobs_worker install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/shared ./shared
COPY --from=builder /app/services/jobs_worker ./services/jobs_worker

ENV PATH="/app/services/jobs_worker/.venv/bin:$PATH" \
    PYTHONPATH=/app/services/jobs_worker/src:/app/shared/src

RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["python", "-c", "from jobs_worker.health import check; check()"]

CMD ["python", "-m", "jobs_worker.main"]
