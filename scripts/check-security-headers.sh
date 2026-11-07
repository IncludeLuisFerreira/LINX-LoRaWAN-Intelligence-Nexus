#!/usr/bin/env sh
# Guarda de CI: HSTS/CSP/Permissions-Policy nos nginx de borda.
# A lógica fica em Python para parsear blocos e ignorar comentários.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/check_security_headers.py" --root "$ROOT"
