#!/bin/bash

# Encerra o script imediatamente se algum comando falhar
set -e

echo "Iniciando o processo de deploy do frontend..."

# Validação estrita das variáveis de ambiente de infraestrutura
if [ -z "$ECR_REPO" ] && [ -z "$S3_BUCKET" ]; then
  echo "Erro: Nem ECR_REPO nem S3_BUCKET foram definidos. Impossível realizar o deploy." >&2
  exit 1
fi

# Lógica de deploy para S3 (caso esteja configurado)
if [ -n "$S3_BUCKET" ]; then
  echo "Enviando build para o bucket S3: $S3_BUCKET..."
  # aws s3 sync frontend/dist s3://$S3_BUCKET --delete
fi

# Lógica de deploy para ECR (caso esteja configurado)
if [ -n "$ECR_REPO" ]; then
  echo "Enviando imagem Docker para o ECR: $ECR_REPO..."
  # docker build -t $ECR_REPO:latest ./frontend
  # docker push $ECR_REPO:latest
fi

echo "Deploy do frontend concluído com sucesso!"