#!/usr/bin/env bash
# Publica a imagem do tenant_app no Docker Hub (MVP) ou no Amazon ECR.
# O contexto padrão é client/tenant_app, criado pela issue #58.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Mantém o build na raiz do repositório para usar o .dockerignore versionado.
cd "$REPO_ROOT"

REGISTRY="dockerhub"
TAG="latest"
PUSH=1
CONTEXT="${TENANT_APP_CONTEXT:-client/tenant_app}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-}"
PLATFORM="${PLATFORM:-linux/amd64}"
DOCKERHUB_REPOSITORY="${DOCKERHUB_REPOSITORY:-includeluisferreira/linx-tenant-app}"
ECR_REPOSITORY="${ECR_REPOSITORY:-linx-tenant-app}"
AWS_REGION="${AWS_REGION:-}"

usage() {
  cat <<'EOF'
Uso: scripts/publish_tenant_app_image.sh [opções]

Opções:
  --registry dockerhub|ecr  Registro de destino (padrão: dockerhub).
  --repository <ref>        Repositório completo da imagem.
                            Docker Hub: includeluisferreira/linx-tenant-app
                            ECR: <conta>.dkr.ecr.<região>.amazonaws.com/linx-tenant-app
  --tag <tag>               Tag da imagem (padrão: latest).
  --context <dir>           Contexto Docker (padrão: client/tenant_app).
  --platform <platform>     Plataforma do build (padrão: linux/amd64).
  --build-only              Apenas build e smoke test; não faz login nem push.
  -h, --help                Mostra esta ajuda.

Variáveis de ambiente:
  TENANT_APP_CONTEXT        Alternativa a --context.
  IMAGE_REPOSITORY          Alternativa a --repository.
  DOCKERHUB_REPOSITORY      Repositório padrão do Docker Hub.
  ECR_REPOSITORY            Nome do repositório ECR (padrão: linx-tenant-app).
  AWS_REGION                Região do ECR (obrigatória no modo ecr com push).
  AWS_ACCOUNT_ID            Conta AWS (opcional; obtida via STS se ausente).

Exemplos:
  docker login
  ./scripts/publish_tenant_app_image.sh --registry dockerhub --tag latest

  AWS_REGION=us-east-1 ./scripts/publish_tenant_app_image.sh --registry ecr

  ./scripts/publish_tenant_app_image.sh --build-only
EOF
}

die() {
  echo "erro: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)
      [[ $# -ge 2 ]] || die "faltou valor para --registry"
      REGISTRY="$2"
      shift 2
      ;;
    --repository)
      [[ $# -ge 2 ]] || die "faltou valor para --repository"
      IMAGE_REPOSITORY="$2"
      shift 2
      ;;
    --tag)
      [[ $# -ge 2 ]] || die "faltou valor para --tag"
      TAG="$2"
      shift 2
      ;;
    --context)
      [[ $# -ge 2 ]] || die "faltou valor para --context"
      CONTEXT="$2"
      shift 2
      ;;
    --platform)
      [[ $# -ge 2 ]] || die "faltou valor para --platform"
      PLATFORM="$2"
      shift 2
      ;;
    --build-only)
      PUSH=0
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *) die "argumento desconhecido: $1" ;;
  esac
done

[[ "$REGISTRY" == "dockerhub" || "$REGISTRY" == "ecr" ]] ||
  die "--registry deve ser dockerhub ou ecr"
[[ -n "$TAG" ]] || die "--tag não pode ser vazio"
[[ -n "$PLATFORM" ]] || die "--platform não pode ser vazio"

if [[ "$CONTEXT" = /* ]]; then
  CONTEXT_DIR="$CONTEXT"
else
  CONTEXT_DIR="${REPO_ROOT}/${CONTEXT}"
fi

[[ -f "${CONTEXT_DIR}/Dockerfile" ]] ||
  die "contexto inválido: ${CONTEXT_DIR}/Dockerfile não encontrado (depende da issue #58)"

IMAGE_REPOSITORY="${IMAGE_REPOSITORY%/}"

if [[ -z "$IMAGE_REPOSITORY" ]]; then
  if [[ "$REGISTRY" == "dockerhub" ]]; then
    IMAGE_REPOSITORY="$DOCKERHUB_REPOSITORY"
  elif [[ "$PUSH" -eq 0 ]]; then
    IMAGE_REPOSITORY="linx-tenant-app"
  else
    command -v aws >/dev/null 2>&1 ||
      die "AWS CLI não encontrado; instale o aws-cli para publicar no ECR"
    [[ -n "$AWS_REGION" ]] || die "defina AWS_REGION para publicar no ECR"
    ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
    IMAGE_REPOSITORY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
  fi
fi

IMAGE_REF="${IMAGE_REPOSITORY}:${TAG}"
REVISION="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"

echo "Contexto: ${CONTEXT_DIR}"
echo "Imagem: ${IMAGE_REF}"
echo "Plataforma: ${PLATFORM}"

# Build reprodutível: sempre parte do Dockerfile versionado e das dependências
# travadas em poetry.lock. As labels ligam a imagem ao repositório e ao commit.
docker build \
  --pull \
  --platform "$PLATFORM" \
  --label "org.opencontainers.image.title=linx-tenant-app" \
  --label "org.opencontainers.image.source=https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus" \
  --label "org.opencontainers.image.revision=${REVISION}" \
  -t "$IMAGE_REF" \
  "$CONTEXT_DIR"

# Smoke test mínimo: falha cedo se a aplicação não puder ser importada.
docker run --rm --platform "$PLATFORM" "$IMAGE_REF" \
  python -c "import tenant_app.app"

if [[ "$PUSH" -eq 0 ]]; then
  echo "Build concluído sem push: ${IMAGE_REF}"
  exit 0
fi

case "$REGISTRY" in
  dockerhub)
    DOCKER_USER="$(docker info 2>/dev/null | sed -n 's/^ *Username: *//p' | head -n 1)"
    [[ -n "$DOCKER_USER" ]] ||
      die "Docker Hub não autenticado; execute docker login antes do push"
    docker push "$IMAGE_REF"
    ;;
  ecr)
    command -v aws >/dev/null 2>&1 || die "AWS CLI não encontrado"
    [[ -n "$AWS_REGION" ]] || die "defina AWS_REGION para publicar no ECR"

    REGISTRY_HOST="${IMAGE_REPOSITORY%%/*}"
    REPOSITORY_NAME="${IMAGE_REPOSITORY#*/}"

    # Cria o repositório ECR na primeira publicação.
    if ! aws ecr describe-repositories \
      --region "$AWS_REGION" \
      --repository-names "$REPOSITORY_NAME" >/dev/null 2>&1; then
      aws ecr create-repository \
        --region "$AWS_REGION" \
        --repository-name "$REPOSITORY_NAME" \
        --image-scanning-configuration scanOnPush=true >/dev/null
    fi

    aws ecr get-login-password --region "$AWS_REGION" |
      docker login --username AWS --password-stdin "$REGISTRY_HOST" >/dev/null
    docker push "$IMAGE_REF"
    ;;
esac

# Confirma que a tag está disponível no registro após o push.
docker manifest inspect "$IMAGE_REF" >/dev/null

echo "Imagem publicada: ${IMAGE_REF}"
echo "Para o provisioner: PROVISION_IMAGE=${IMAGE_REF}"
