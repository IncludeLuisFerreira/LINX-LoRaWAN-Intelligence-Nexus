#!/usr/bin/env bash
# Gera os stubs Python gRPC (linx_agent_pb2.py / linx_agent_pb2_grpc.py) a
# partir de proto/linx_agent.proto para o pacote compartilhado `linx_shared`,
# dono único do contrato do AgentBridge (#215).
#
# Uso:
#     bash scripts/gen_proto.sh
#
# Requer grpcio-tools instalado em linx_core/shared (poetry install).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="linx_core/shared/src/linx_shared/grpc"

poetry -C linx_core/shared run python -m grpc_tools.protoc \
  -I "$ROOT/proto" \
  --python_out="$ROOT/$OUT" \
  --grpc_python_out="$ROOT/$OUT" \
  "$ROOT/proto/linx_agent.proto"

# grpc_tools.protoc gera `import linx_agent_pb2` (absoluto), o que quebra
# quando o arquivo vive dentro do pacote linx_shared.grpc. Corrige para
# import relativo.
sed -i 's/^import linx_agent_pb2 as linx__agent__pb2$/from . import linx_agent_pb2 as linx__agent__pb2/' \
  "$OUT/linx_agent_pb2_grpc.py"

echo "Stubs gRPC gerados em $OUT"
