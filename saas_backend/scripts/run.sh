#!/usr/bin/env bash
# Sobe os microserviços do módulo SaaS em modo desenvolvimento:
#   identity_api  -> REST  (http://localhost:8000)
#   agent_bridge  -> gRPC  (localhost:50051)
# Ctrl+C encerra os dois.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

pids=()
cleanup() {
  echo ""
  echo "Encerrando serviços..."
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Subindo identity_api (REST :8000)..."
poetry -C identity_api run uvicorn identity_api.main:app --reload &
pids+=("$!")

echo "Subindo agent_bridge (gRPC :50051)..."
poetry -C agent_bridge run python -m agent_bridge.server &
pids+=("$!")

echo "Serviços rodando. Pressione Ctrl+C para encerrar."
wait
