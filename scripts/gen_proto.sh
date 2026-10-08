#!/usr/bin/env bash
# Gera os stubs Python gRPC (linx_agent_pb2.py / linx_agent_pb2_grpc.py) a
# partir de proto/linx_agent.proto, para a biblioteca compartilhada do Linx Core
# (package linx_shared), o Client Agent (package agent) e o tenant app
# template (package tenant).
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
    "$ROOT/proto/linx_agent.proto"
}

gen linx_core/shared linx_core/shared/src/linx_shared/grpc
gen middleware/services/client_agent middleware/services/client_agent/src/agent/grpc
gen client client/src/tenant/grpc

# grpc_tools.protoc gera `import linx_agent_pb2` (absoluto), o que quebra
# quando o arquivo vive dentro de um pacote (linx_shared.grpc / agent.grpc /
# tenant.grpc). Corrige para import relativo.
for grpc_file in \
  linx_core/shared/src/linx_shared/grpc/linx_agent_pb2_grpc.py \
  middleware/services/client_agent/src/agent/grpc/linx_agent_pb2_grpc.py \
  client/src/tenant/grpc/linx_agent_pb2_grpc.py; do
  sed -i 's/^import linx_agent_pb2 as linx__agent__pb2$/from . import linx_agent_pb2 as linx__agent__pb2/' "$grpc_file"
done

echo "Stubs gRPC gerados em linx_core/shared/src/linx_shared/grpc, middleware/services/client_agent/src/agent/grpc e client/src/tenant/grpc"
