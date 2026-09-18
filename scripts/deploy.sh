#!/bin/bash
set -e

cd ~/LINX-LoRaWAN-Intelligence-Nexus

echo "==> Atualizando código..."
git pull

echo "==> Build e deploy..."
docker compose -f deploy/docker-compose.prod.yml up -d --build

echo "==> Limpando imagens antigas..."
docker image prune -f

echo "==> Deploy concluído!"
docker compose -f deploy/docker-compose.prod.yml ps