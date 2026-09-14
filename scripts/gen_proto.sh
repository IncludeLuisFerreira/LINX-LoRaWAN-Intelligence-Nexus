#!/usr/bin/env bash
# Gera os stubs Python gRPC (saas_agent_pb2.py / saas_agent_pb2_grpc.py) a
# partir de proto/saas_agent.proto, para o SaaS Backend (package linx) e o
# Client Agent (package agent).
#
# Uso:
#     bash scripts/gen_proto.sh
#
# Requer grpcio-tools instalado em cada módulo (poetry install).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

gen() {
  local module="$1"
  local out="$2"
  poetry -C "$module" run python -m grpc_tools.protoc \
    -I "$ROOT/proto" \
    --python_out="$ROOT/$out" \
    --grpc_python_out="$ROOT/$out" \
    "$ROOT/proto/saas_agent.proto"
}

gen saas_backend saas_backend/src/linx/grpc
gen client_agent_api client_agent_api/src/agent/grpc

# grpc_tools.protoc gera `import saas_agent_pb2` (absoluto), o que quebra
# quando o arquivo vive dentro de um pacote (linx.grpc / agent.grpc).
# Corrige para import relativo.
for grpc_file in \
  saas_backend/src/linx/grpc/saas_agent_pb2_grpc.py \
  client_agent_api/src/agent/grpc/saas_agent_pb2_grpc.py; do
  sed -i 's/^import saas_agent_pb2 as saas__agent__pb2$/from . import saas_agent_pb2 as saas__agent__pb2/' "$grpc_file"
done

echo "Stubs gRPC gerados em saas_backend/src/linx/grpc e client_agent_api/src/agent/grpc"
