#!/usr/bin/env bash
# Emite/renova o certificado Let's Encrypt do dashboard e publica os PEMs
# consumidos pela borda TLS (client/frontend/nginx-tls.conf).
#
# Uso:
#   FRONTEND_DOMAIN=dashboard.exemplo.com LE_EMAIL=admin@exemplo.com \
#     ./scripts/frontend-cert.sh issue
#   FRONTEND_DOMAIN=dashboard.exemplo.com ./scripts/frontend-cert.sh renew
#
# O desafio HTTP-01 é servido pelo serviço `frontend-tls` em
# /.well-known/acme-challenge/ a partir de client/certbot/www.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$ROOT/docker-compose.yml"
CERTS_DIR="$ROOT/certs"
LE_DIR="$ROOT/certbot/conf"
WWW_DIR="$ROOT/certbot/www"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi

DOMAIN="${FRONTEND_DOMAIN:-}"
EMAIL="${LE_EMAIL:-}"

log() { printf '%s\n' "$*"; }
fail() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Uso: $(basename "$0") <issue|renew|status>

  issue   Sobe a borda, emite o certificado e publica em client/certs/.
  renew   Renova via certbot, republica os PEMs e recarrega o nginx.
  status  Mostra a validade do certificado publicado.

Variáveis de ambiente (ou client/.env):
  FRONTEND_DOMAIN  domínio público do dashboard (obrigatório)
  LE_EMAIL         e-mail para o Let's Encrypt (obrigatório em issue)
  LE_STAGING=1     usa os servidores de staging do Let's Encrypt
EOF
}

require_domain() {
  [ -n "$DOMAIN" ] || fail "defina FRONTEND_DOMAIN (ou client/.env)."
}

extra_args() {
  if [ "${LE_STAGING:-0}" = "1" ]; then
    printf '%s' "--staging"
  fi
}

# Certificado provisório apenas para o nginx subir e responder ao desafio
# HTTP-01. É substituído pelo certificado real ao final de `issue`.
bootstrap_cert() {
  [ -f "$CERTS_DIR/fullchain.pem" ] && [ -f "$CERTS_DIR/privkey.pem" ] && return 0

  log "Gerando certificado bootstrap (autoassinado) para iniciar a borda..."
  mkdir -p "$CERTS_DIR"
  local san="DNS:${DOMAIN:-localhost}"
  # A chave nunca deve nascer legível por outros usuários. O umask restrito
  # vale só na geração (subshell) e é restaurado ao sair dela; o chmod abaixo
  # reforça a permissão da chave publicada.
  if ! (
    umask 077
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
      -keyout "$CERTS_DIR/privkey.pem" \
      -out "$CERTS_DIR/fullchain.pem" \
      -subj "/C=BR/O=LINX/CN=${DOMAIN:-localhost}" \
      -addext "subjectAltName=$san" >/dev/null 2>&1
  ); then
    fail "falha ao gerar o certificado bootstrap autoassinado."
  fi
  chmod 600 "$CERTS_DIR/privkey.pem"
  chmod 644 "$CERTS_DIR/fullchain.pem"
}

publish_cert() {
  local live="$LE_DIR/live/$DOMAIN"
  [ -f "$live/fullchain.pem" ] || fail "certificado não encontrado em $live"
  [ -f "$live/privkey.pem" ] || fail "chave não encontrada em $live"

  mkdir -p "$CERTS_DIR"
  install -m 0644 "$live/fullchain.pem" "$CERTS_DIR/fullchain.pem"
  install -m 0600 "$live/privkey.pem" "$CERTS_DIR/privkey.pem"
  log "Certificado publicado em $CERTS_DIR"
}

reload_edge() {
  # O reload exige o container de pé (ex.: host reiniciado desde o `issue`).
  # Sobe/reconcilia o serviço antes de recarregar e falha com mensagem clara.
  if ! docker compose -f "$COMPOSE" up -d frontend-tls; then
    fail "não foi possível subir o serviço frontend-tls."
  fi
  if ! docker compose -f "$COMPOSE" exec -T frontend-tls nginx -s reload; then
    fail "falha ao recarregar o nginx: frontend-tls não está rodando?"
  fi
}

cmd_issue() {
  require_domain
  [ -n "$EMAIL" ] || fail "defina LE_EMAIL (ou client/.env)."
  command -v docker >/dev/null 2>&1 || fail "docker não encontrado."
  command -v openssl >/dev/null 2>&1 || fail "openssl não encontrado."

  mkdir -p "$WWW_DIR" "$LE_DIR" "$CERTS_DIR"
  bootstrap_cert

  log "Subindo a borda TLS para o desafio HTTP-01..."
  docker compose -f "$COMPOSE" up -d frontend-tls

  log "Solicitando certificado para $DOMAIN..."
  # shellcheck disable=SC2046
  docker compose -f "$COMPOSE" run --rm certbot \
    certonly --webroot -w /var/www/certbot \
    -d "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email \
    $(extra_args)

  publish_cert
  reload_edge
  log "HTTPS ativo. Verifique: curl -I https://$DOMAIN"
}

cmd_renew() {
  require_domain
  command -v docker >/dev/null 2>&1 || fail "docker não encontrado."

  log "Renovando certificados..."
  # shellcheck disable=SC2046
  docker compose -f "$COMPOSE" run --rm certbot \
    renew --webroot -w /var/www/certbot $(extra_args)

  publish_cert
  reload_edge
  log "Renovação concluída."
}

cmd_status() {
  require_domain
  local cert="$CERTS_DIR/fullchain.pem"
  [ -f "$cert" ] || fail "certificado publicado não encontrado em $cert."
  openssl x509 -in "$cert" -noout -subject -dates -ext subjectAltName
}

case "${1:-}" in
  issue) cmd_issue ;;
  renew) cmd_renew ;;
  status) cmd_status ;;
  *) usage; exit 1 ;;
esac
