#!/usr/bin/env bash
# Gera os stubs Python gRPC dos contratos em proto/ para o pacote
# compartilhado `linx_shared`, dono único dos contratos gRPC da plataforma.
#
# Contratos:
#   - linx_agent.proto              -> AgentBridge
#   - linx_docker_provisioner.proto -> DockerProvisioner
#
# Uso:
#     bash scripts/gen_proto.sh
#
# Requer grpcio-tools instalado em linx_core/shared (poetry install).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="linx_core/shared/src/linx_shared/grpc"

generate_stub() {
  local proto_name="$1"

  poetry -C linx_core/shared run python -m grpc_tools.protoc \
    -I "$ROOT/proto" \
    --python_out="$ROOT/$OUT" \
    --grpc_python_out="$ROOT/$OUT" \
    "$ROOT/proto/${proto_name}.proto"

  # grpc_tools.protoc gera imports absolutos (`import <proto>_pb2`), o que
  # quebra quando o arquivo vive dentro do pacote linx_shared.grpc. Corrige
  # para import relativo.
  sed -i "s/^import ${proto_name}_pb2 as /from . import ${proto_name}_pb2 as /" \
    "$OUT/${proto_name}_pb2_grpc.py"
}

generate_stub "linx_agent"
generate_stub "linx_docker_provisioner"

echo "Stubs gRPC gerados em $OUT"
