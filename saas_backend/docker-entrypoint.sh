#! /bin/sh

set -e

echo "Applying database migrations..."
max_attempts=30
attempt=1
until alembic upgrade head; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "ERROR: migrations failed after ${max_attempts} attempts. Aborting." >&2
        exit 1
    fi
    echo "Migration failed (database not ready?). Retrying in 3s... (${attempt}/${max_attempts})"
    attempt=$((attempt + 1))
    sleep 3
done

echo "Starting uvicorn..."
exec uvicorn linx.main:app --host 0.0.0.0 --port 8000
