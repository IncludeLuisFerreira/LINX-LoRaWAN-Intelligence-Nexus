#!/usr/bin/env bash
# Sobe os microserviços do módulo SaaS em modo desenvolvimento:
#   identity_api       -> REST  (http://localhost:8000)
#   agent_bridge       -> gRPC  (localhost:50051)
#   docker_provisioner -> gRPC  (localhost:50052)
#   jobs_worker        -> consome RabbitMQ e chama o docker_provisioner
# Ctrl+C encerra os quatro.
#
# Requer um RabbitMQ acessível em RABBITMQ_AMQP_URL (por exemplo,
# `docker compose up -d rabbitmq` ou um broker local na porta 5672).
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
poetry -C services/identity_api run uvicorn identity_api.main:app --reload &
pids+=("$!")

echo "Subindo agent_bridge (gRPC :50051)..."
poetry -C services/agent_bridge run python -m agent_bridge.server &
pids+=("$!")

echo "Subindo docker_provisioner (gRPC :50052)..."
# O .env compartilhado tem GRPC_PORT=50051 (agent_bridge); sobrescreve para
# evitar que os dois servidores tentem a mesma porta no modo host.
GRPC_HOST=127.0.0.1 GRPC_PORT=50052 \
  poetry -C services/docker_provisioner run python -m docker_provisioner.server &
pids+=("$!")

echo "Subindo jobs_worker (RabbitMQ)..."
poetry -C services/jobs_worker run python -m jobs_worker.main &
pids+=("$!")

echo "Serviços rodando. Pressione Ctrl+C para encerrar."
wait
