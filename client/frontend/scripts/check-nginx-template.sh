#!/usr/bin/env sh
# Valida que o nginx do dashboard sobe em execução isolada.
#
# O entrypoint da imagem oficial só substitui variáveis presentes no ambiente.
# Se o template usar `${VAR}` sem default no Dockerfile (ex.: SERVICE_TOKEN),
# o envsubst deixa o literal no config e o `nginx -t` falha — o container não
# sobe em `docker run` isolado, embora funcione no compose. Este script builda
# a imagem real e roda `nginx -t` sem nenhuma variável extra, reproduzindo o
# cenário que quebra.
#
# Uso: client/frontend/scripts/check-nginx-template.sh [tag]
set -eu

IMAGE="${1:-lynx-frontend:nginx-check}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTEXT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Build da imagem do dashboard ($IMAGE)..."
docker build -t "$IMAGE" "$CONTEXT"

echo "Rodando 'nginx -t' sem variáveis de ambiente extras..."
if docker run --rm "$IMAGE" nginx -t; then
    echo "OK: template do nginx válido em execução isolada."
else
    echo "FALHA: 'nginx -t' quebrou em execução isolada." >&2
    echo "Verifique se toda \${VAR} do nginx.conf tem default no Dockerfile." >&2
    exit 1
fi
