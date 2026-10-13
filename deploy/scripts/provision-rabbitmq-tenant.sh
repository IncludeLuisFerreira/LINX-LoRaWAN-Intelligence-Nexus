#!/usr/bin/env bash
# Provisiona o usuário e as permissões RabbitMQ de um tenant.
#
# Deriva a senha determinística (HMAC-SHA256 de APP_ID com
# RABBITMQ_TENANT_SECRET) de forma idêntica a
# `linx_shared.core.rabbitmq.derive_tenant_password` e cria o usuário
# `tenant.{APP_ID}` com configure/write/read restritos ao namespace
# `linx.telemetry.{APP_ID}`.
#
# Uso:
#   APP_ID=<uuid> RABBITMQ_TENANT_SECRET=<segredo> \
#   RABBITMQ_MANAGEMENT_URL=http://localhost:15672 \
#   RABBITMQ_ADMIN_USER=linx RABBITMQ_ADMIN_PASSWORD=changeme \
#   ./provision-rabbitmq-tenant.sh
set -euo pipefail

: "${APP_ID:?APP_ID é obrigatório}"
: "${RABBITMQ_TENANT_SECRET:?RABBITMQ_TENANT_SECRET é obrigatório}"

MANAGEMENT_URL="${RABBITMQ_MANAGEMENT_URL:-http://localhost:15672}"
ADMIN_USER="${RABBITMQ_ADMIN_USER:-linx}"
ADMIN_PASSWORD="${RABBITMQ_ADMIN_PASSWORD:-changeme}"
VHOST="${RABBITMQ_VHOST:-/}"

USER="tenant.${APP_ID}"
PASSWORD="$(
  printf '%s' "$APP_ID" \
    | openssl dgst -sha256 -hmac "$RABBITMQ_TENANT_SECRET" -binary \
    | openssl base64 -A \
    | tr '+/' '-_' \
    | tr -d '='
)"
PASSWORD="${PASSWORD:0:40}"

# Vhost "/" precisa ser URL-encoded como %2F no caminho da management API.
ENCODED_VHOST="${VHOST//\//%2F}"
REGEX="^linx\\\\.telemetry\\\\.${APP_ID}(\\\\.|$)"

echo "Provisionando usuário ${USER} no vhost ${VHOST}..."
curl -fsS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
  -X PUT "${MANAGEMENT_URL}/api/users/${USER}" \
  -H 'content-type: application/json' \
  -d "{\"password\": \"${PASSWORD}\", \"tags\": \"\"}"

curl -fsS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" \
  -X PUT "${MANAGEMENT_URL}/api/permissions/${ENCODED_VHOST}/${USER}" \
  -H 'content-type: application/json' \
  -d "{\"configure\": \"${REGEX}\", \"write\": \"${REGEX}\", \"read\": \"${REGEX}\"}"

echo "OK. RABBIT_URL do tenant:"
echo "amqp://${USER}:${PASSWORD}@<amqp-host>/${ENCODED_VHOST}"
