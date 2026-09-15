#! /bin/sh

set -e

echo "Applying database migrations...."
until alembic upgrade head; do
    echo "Migration failed (database not ready?). Retrying in 3s..."
    sleep 3
done

echo "Starting uvicorn..."
exec uvicorn linx.main:app --host 0.0.0.0 --port 8080