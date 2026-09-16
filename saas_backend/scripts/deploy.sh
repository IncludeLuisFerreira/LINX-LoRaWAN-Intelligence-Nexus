#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and set a strong POSTGRES_PASSWORD." >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
echo "Pulling latest code on branch '${branch}'..."
git pull --ff-only

echo "Building and starting containers..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Status:"
docker compose -f docker-compose.prod.yml ps
