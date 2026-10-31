#!/usr/bin/env bash
set -euo pipefail
NETWORK="${1:-linx-network}"
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"
echo "network ${NETWORK} pronta"
