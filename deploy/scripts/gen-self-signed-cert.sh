#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${TLS_CERT_DIR:-$SCRIPT_DIR/../certs}"
CERT_HOST="${TLS_CERT_HOST:-localhost}"
CERT_DAYS="${TLS_CERT_DAYS:-365}"

CERT_FILE="$CERT_DIR/fullchain.pem"
KEY_FILE="$CERT_DIR/privkey.pem"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl não encontrado. Instale o openssl e tente novamente." >&2
  exit 1
fi

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "Certificado já existe em $CERT_DIR (use FORCE=1 para regenerar)."
  exit 0
fi

mkdir -p "$CERT_DIR"

if [[ "$CERT_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="DNS:localhost,IP:127.0.0.1,IP:$CERT_HOST"
else
  SAN="DNS:localhost,DNS:$CERT_HOST,IP:127.0.0.1"
fi

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -days "$CERT_DAYS" \
  -subj "/C=BR/ST=SP/L=Sao Paulo/O=LINX/CN=$CERT_HOST" \
  -addext "subjectAltName=$SAN" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth"

chmod 600 "$KEY_FILE"

echo "Certificado self-signed gerado:"
echo "  cert: $CERT_FILE"
echo "  key:  $KEY_FILE"
