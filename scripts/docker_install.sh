#!/bin/bash
set -e

echo "==> Atualizando Ubuntu..."
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

echo "==> Instalando dependências..."
sudo apt install -y ca-certificates curl

echo "==> Configurando repositório oficial do Docker..."
sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "==> Instalando Docker e Docker Compose..."
sudo apt update

sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

echo "==> Habilitando Docker..."
sudo systemctl enable docker
sudo systemctl start docker

echo "==> Configurando usuário atual..."
sudo usermod -aG docker "$USER"

echo ""
echo "========================================"
echo " Docker instalado com sucesso!"
echo "========================================"
docker --version || true
sudo docker compose version

echo ""
echo "IMPORTANTE:"
echo "Saia da sessão SSH e entre novamente para usar"
echo 'docker sem sudo.'
echo ""
echo "Depois teste:"
echo "  docker ps"
echo "  docker compose version"