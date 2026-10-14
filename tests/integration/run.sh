#!/usr/bin/env bash
# Sobe a stack de integração, roda os testes ponta-a-ponta e derruba tudo.
#
# Uso:
#   tests/integration/run.sh            # todos os testes
#   tests/integration/run.sh -k mqtt    # passa flags ao pytest
#
# Diagnóstico: se um container não subir, a suíte aborta listando o serviço
# fora do ar e como ver os logs.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v poetry >/dev/null 2>&1; then
  echo "ERROR: poetry não encontrado no PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker não está acessível (daemon parado?)." >&2
  exit 1
fi

echo "==> Instalando dependências dos testes de integração..."
poetry install --no-interaction --quiet

echo "==> Rodando a suíte de integração (sobe/derruba a stack)..."
exec poetry run pytest "$@"
