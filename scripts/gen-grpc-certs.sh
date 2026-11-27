#!/usr/bin/env bash
# Gera CA, certificado do agent_bridge e par cliente para o mTLS gRPC (#82).
# Artefatos ficam em certs/grpc/ (ignorados pelo git). As chaves da CA nunca
# são montadas nos containers — apenas a CA pública e os pares de cada lado
# do canal.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${GRPC_CERT_DIR:-$SCRIPT_DIR/../certs/grpc}"
DAYS="${GRPC_CERT_DAYS:-365}"
SERVER_HOST="${GRPC_SERVER_HOST:-agent_bridge}"
CLIENT_NAME="${GRPC_CLIENT_NAME:-linx-client-agent}"
# UID/GID do usuário dos containers (appuser, UID 1000 nos Dockerfiles).
# As chaves/diretórios são gerados com o owner de quem executa este script;
# o chown abaixo garante que o container consiga ler os arquivos montados.
CERT_UID="${GRPC_CERT_UID:-1000}"

CA_DIR="$CERT_DIR/ca"
SERVER_DIR="$CERT_DIR/server"
CLIENT_DIR="$CERT_DIR/client"
CA_CERT="$CA_DIR/ca.crt"
CA_KEY="$CA_DIR/ca.key"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl não encontrado. Instale o openssl e tente novamente." >&2
  exit 1
fi

if [ -f "$CA_CERT" ] && [ -f "$CA_KEY" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "CA gRPC já existe em $CERT_DIR (use FORCE=1 para regenerar tudo)."
  exit 0
fi

umask 077
mkdir -p "$CA_DIR" "$SERVER_DIR" "$CLIENT_DIR"

# --- CA -------------------------------------------------------------------
openssl req -x509 -newkey rsa:2048 -sha256 -nodes \
  -keyout "$CA_KEY" \
  -out "$CA_CERT" \
  -days "$DAYS" \
  -subj "/C=BR/ST=SP/L=Sao Paulo/O=LINX/CN=LINX gRPC CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" >/dev/null 2>&1

# --- Certificado do servidor (agent_bridge) -------------------------------
SAN="DNS:localhost,DNS:agent_bridge,DNS:agent-bridge,IP:127.0.0.1"
if [[ "$SERVER_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="$SAN,IP:$SERVER_HOST"
elif [[ "$SERVER_HOST" != "localhost" && "$SERVER_HOST" != "agent_bridge" \
  && "$SERVER_HOST" != "agent-bridge" ]]; then
  SAN="$SAN,DNS:$SERVER_HOST"
fi

cat > "$SERVER_DIR/server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$SAN
EOF

openssl req -newkey rsa:2048 -sha256 -nodes \
  -keyout "$SERVER_DIR/server.key" \
  -out "$SERVER_DIR/server.csr" \
  -subj "/C=BR/ST=SP/L=Sao Paulo/O=LINX/CN=$SERVER_HOST" >/dev/null 2>&1
openssl x509 -req -in "$SERVER_DIR/server.csr" \
  -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
  -out "$SERVER_DIR/server.crt" -days "$DAYS" -sha256 \
  -extfile "$SERVER_DIR/server.ext" >/dev/null 2>&1

# --- Certificado do cliente (client_agent) --------------------------------
cat > "$CLIENT_DIR/client.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
subjectAltName=DNS:$CLIENT_NAME
EOF

openssl req -newkey rsa:2048 -sha256 -nodes \
  -keyout "$CLIENT_DIR/client.key" \
  -out "$CLIENT_DIR/client.csr" \
  -subj "/C=BR/ST=SP/L=Sao Paulo/O=LINX/CN=$CLIENT_NAME" >/dev/null 2>&1
openssl x509 -req -in "$CLIENT_DIR/client.csr" \
  -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
  -out "$CLIENT_DIR/client.crt" -days "$DAYS" -sha256 \
  -extfile "$CLIENT_DIR/client.ext" >/dev/null 2>&1

chmod 700 "$CA_DIR" "$SERVER_DIR" "$CLIENT_DIR"
chmod 600 "$CA_KEY" "$SERVER_DIR/server.key" "$CLIENT_DIR/client.key"
chmod 644 "$CA_CERT" "$SERVER_DIR/server.crt" "$CLIENT_DIR/client.crt"
# Garante que um container rodando como appuser (UID 1000) consiga ler as
# chaves 0600 e atravessar os diretórios 0700 quando os arquivos forem montados.
# Ignora falha (ex.: sem privilégio para chown): nesse caso gere com sudo ou
# ajuste a propriedade manualmente (`sudo chown -R 1000:1000 certs/grpc`).
chown -R "$CERT_UID":"$CERT_UID" "$CERT_DIR" 2>/dev/null || true

openssl verify -CAfile "$CA_CERT" \
  "$SERVER_DIR/server.crt" "$CLIENT_DIR/client.crt"

echo "Certificados mTLS gRPC gerados em $CERT_DIR:"
echo "  CA (pública): $CA_CERT"
echo "  servidor:     $SERVER_DIR/server.crt + server.key"
echo "  cliente:      $CLIENT_DIR/client.crt + client.key"
