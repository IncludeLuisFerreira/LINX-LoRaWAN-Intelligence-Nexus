#!/usr/bin/env bash
# Garante a rede compartilhada entre os stacks (idempotente).
#
# Uso:
#   scripts/bootstrap-network.sh [nome-da-rede]
#
# O nome default é `linx-network`; a variável LINX_NETWORK permite isolar
# a stack de testes em outra rede.
set -euo pipefail

NETWORK="${1:-${LINX_NETWORK:-linx-network}}"
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"
echo "network ${NETWORK} pronta"
