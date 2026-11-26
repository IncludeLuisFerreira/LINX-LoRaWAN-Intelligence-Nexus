#!/usr/bin/env sh
# Valida o config da borda HTTPS do dashboard (client/frontend/nginx-tls.conf).
#
# 1) checa diretivas obrigatórias (redirect 80->443, ACME webroot, TLS, HSTS,
#    proxy para o serviço `frontend` e repasse de Upgrade para WSS);
# 2) gera um certificado autoassinado descartável e roda `nginx -t` na imagem
#    oficial, garantindo que a sintaxe é válida sem depender de cert real.
#
# Uso: client/frontend/scripts/check-nginx-tls.sh [--static-only] [imagem]
#   --static-only  só checa as diretivas (útil sem daemon Docker).
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../nginx-tls.conf"
STATIC_ONLY=0
if [ "${1:-}" = "--static-only" ]; then
  STATIC_ONLY=1
  shift
fi
IMAGE="${1:-nginx:1.27-alpine}"

[ -f "$CONFIG" ] || {
  echo "FALHA: $CONFIG não encontrado." >&2
  exit 1
}

assert_contains() {
  if ! grep -qF "$1" "$CONFIG"; then
    echo "FALHA: nginx-tls.conf não contém: $1" >&2
    exit 1
  fi
}

assert_contains 'listen 80;'
assert_contains 'location /.well-known/acme-challenge/'
assert_contains 'root /var/www/certbot;'
assert_contains 'return 301 https://$host$request_uri;'
assert_contains 'listen 443 ssl;'
assert_contains 'ssl_certificate     /etc/nginx/certs/fullchain.pem;'
assert_contains 'ssl_certificate_key /etc/nginx/certs/privkey.pem;'
assert_contains 'Strict-Transport-Security'
assert_contains 'resolver 127.0.0.11'
assert_contains 'set $frontend "frontend:80";'
assert_contains 'proxy_set_header X-Forwarded-Proto https;'
assert_contains 'map $http_upgrade $connection_upgrade'

if [ "$STATIC_ONLY" -eq 1 ]; then
  echo "OK: diretivas obrigatórias presentes (nginx -t ignorado)."
  exit 0
fi

command -v openssl >/dev/null 2>&1 || {
  echo "FALHA: openssl não encontrado." >&2
  exit 1
}
command -v docker >/dev/null 2>&1 || {
  echo "FALHA: docker não encontrado." >&2
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -subj "/CN=nginx-tls-check" \
  -keyout "$TMP/privkey.pem" \
  -out "$TMP/fullchain.pem" >/dev/null 2>&1

echo "Rodando 'nginx -t' com certificado descartável ($IMAGE)..."
if docker run --rm \
  -v "$CONFIG:/etc/nginx/conf.d/default.conf:ro" \
  -v "$TMP:/etc/nginx/certs:ro" \
  "$IMAGE" nginx -t; then
  echo "OK: config da borda TLS válido."
else
  echo "FALHA: 'nginx -t' reprovou o config da borda TLS." >&2
  exit 1
fi
