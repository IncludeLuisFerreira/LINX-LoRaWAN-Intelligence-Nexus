#!/usr/bin/env bash
# Gera a CA e o certificado do servidor TLS do Mosquitto (issue #81).
#
# Uso:
#   MQTT_TLS_HOST=mosquitto infra/scripts/gen-mosquitto-certs.sh
#
# Arquivos gerados em infra/configuration/mosquitto/certs/ (NAO versionados):
#   ca.crt, ca.key, server.crt, server.key
#
# O listener 8883 usa server.crt/server.key; os clientes (ChirpStack, gateway
# bridge, routing e probes) confiam na CA via ca.crt. `MQTT_TLS_HOST` define o
# host extra incluido no SAN — o padrao `mosquitto` e o nome do servico no
# Compose. `FORCE=1` regenera tudo (invalida certificados ja distribuidos).
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${MQTT_TLS_CERT_DIR:-$SCRIPT_DIR/../configuration/mosquitto/certs}"
CERT_HOST="${MQTT_TLS_HOST:-mosquitto}"
CERT_DAYS="${MQTT_TLS_DAYS:-365}"

CA_KEY="$CERT_DIR/ca.key"
CA_CERT="$CERT_DIR/ca.crt"
SERVER_KEY="$CERT_DIR/server.key"
SERVER_CERT="$CERT_DIR/server.crt"
SERVER_CSR="$CERT_DIR/server.csr"
CA_SRL="$CERT_DIR/ca.srl"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl nao encontrado. Instale o openssl e tente novamente." >&2
  exit 1
fi

if [ -f "$CA_KEY" ] && [ -f "$CA_CERT" ] &&
   [ -f "$SERVER_KEY" ] && [ -f "$SERVER_CERT" ] &&
   [ "${FORCE:-0}" != "1" ]; then
  echo "Certificados TLS ja existem em $CERT_DIR (use FORCE=1 para regenerar)."
  exit 0
fi

mkdir -p "$CERT_DIR"

# O hostname do cliente precisa casar com o SAN. Sempre inclui localhost e
# 127.0.0.1 para os probes que rodam dentro do container do broker.
if [[ "$CERT_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="DNS:localhost,IP:127.0.0.1,IP:$CERT_HOST"
else
  SAN="DNS:localhost,DNS:mosquitto,IP:127.0.0.1"
  if [ "$CERT_HOST" != "mosquitto" ]; then
    SAN="$SAN,DNS:$CERT_HOST"
  fi
fi

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$CA_KEY" \
  -out "$CA_CERT" \
  -days "$CERT_DAYS" \
  -subj "/C=BR/ST=SP/L=Sao Paulo/O=LINX/CN=LINX MQTT CA"

openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$SERVER_KEY" \
  -out "$SERVER_CSR" \
  -subj "/C=BR/ST=SP/L=Sao Paulo/O=LINX/CN=$CERT_HOST"

openssl x509 -req -in "$SERVER_CSR" \
  -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
  -out "$SERVER_CERT" \
  -days "$CERT_DAYS" \
  -extfile <(
    printf 'subjectAltName=%s\n' "$SAN"
    printf 'basicConstraints=critical,CA:FALSE\n'
    printf 'keyUsage=critical,digitalSignature,keyEncipherment\n'
    printf 'extendedKeyUsage=serverAuth\n'
  )

rm -f "$SERVER_CSR" "$CA_SRL"

chmod 0600 "$CA_KEY"
chmod 0644 "$CA_CERT" "$SERVER_CERT"
# O broker roda como uid 1883 e o compose monta o diretorio read-only; a
# chave do servidor precisa ser legivel por ele (mesma abordagem do
# mosquitto.passwd). A ca.key nunca e montada nos containers.
chmod 0644 "$SERVER_KEY"

echo "Certificados TLS gerados em $CERT_DIR:"
echo "  CA:    $CA_CERT"
echo "  cert:  $SERVER_CERT"
echo "  key:   $SERVER_KEY"
echo "  SAN:   $SAN"
echo "NAO versionar estes arquivos (.gitignore)."
