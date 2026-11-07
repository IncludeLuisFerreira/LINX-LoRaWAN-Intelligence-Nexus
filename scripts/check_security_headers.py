#!/usr/bin/env python3
"""Guarda de CI dos headers de segurança dos nginx de borda.

Regras:
- todo server block precisa de CSP e Permissions-Policy;
- server com TLS (443/ssl_certificate) precisa também de HSTS;
- toda location que declara add_header repete os headers exigidos;
- comentários não contam;
- o frontend HTTP-only não pode emitir HSTS.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CSP = "Content-Security-Policy"
HSTS = "Strict-Transport-Security"
PERMISSIONS = "Permissions-Policy"

REQUIRED = {
    "deploy/nginx/nginx.conf": (CSP, PERMISSIONS),
    "client/frontend/nginx.conf": (CSP, PERMISSIONS),
}
FORBIDDEN = {
    "client/frontend/nginx.conf": (HSTS,),
}

SERVER_RE = re.compile(r"^\s*server\s*\{", re.MULTILINE)
LOCATION_RE = re.compile(r"^\s*location\s+[^{]+\{", re.MULTILINE)
HEADER_RE = re.compile(r"^\s*add_header\s+([A-Za-z0-9-]+)", re.MULTILINE)


def strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def block_content(text: str, start: int) -> str:
    open_brace = text.find("{", start)
    if open_brace < 0:
        raise ValueError("bloco sem '{'")
    depth = 0
    for index in range(open_brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1 : index]
    raise ValueError("bloco sem '}'")


def top_level_headers(content: str) -> set[str]:
    headers: set[str] = set()
    depth = 0
    for line in content.splitlines():
        if depth == 0:
            match = HEADER_RE.match(line)
            if match:
                headers.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return headers


def check_file(root: Path, relative: str) -> list[str]:
    path = root / relative
    if not path.is_file():
        return [f"{relative}: arquivo não encontrado"]

    text = strip_comments(path.read_text())
    errors: list[str] = []
    found_server = False

    for server_match in SERVER_RE.finditer(text):
        found_server = True
        content = block_content(text, server_match.start())
        prologue = content.split("location", 1)[0]
        tls = "443" in prologue or "ssl_certificate" in prologue
        required = set(REQUIRED[relative])
        if tls:
            required.add(HSTS)

        server_headers = top_level_headers(content)
        for header in sorted(required - server_headers):
            errors.append(
                f"{relative}: server block sem {header} no nível do server"
            )
        for header in sorted(set(FORBIDDEN.get(relative, ())) & server_headers):
            errors.append(
                f"{relative}: {header} não deve ser emitido por este nginx"
            )

        for location_match in LOCATION_RE.finditer(content):
            location = block_content(content, location_match.start())
            headers = top_level_headers(location)
            if not headers:
                continue
            for header in sorted(required - headers):
                errors.append(
                    f"{relative}: location com add_header sem {header}"
                )
            for header in sorted(
                set(FORBIDDEN.get(relative, ())) & headers
            ):
                errors.append(
                    f"{relative}: location não deve emitir {header}"
                )

    if not found_server:
        errors.append(f"{relative}: nenhum server block encontrado")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="raiz do repositório (para fixtures de teste)",
    )
    args = parser.parse_args()

    errors: list[str] = []
    for relative in REQUIRED:
        errors.extend(check_file(args.root, relative))

    if errors:
        for error in errors:
            print(f"FALHA: {error}", file=sys.stderr)
        print("Guarda de headers falhou.", file=sys.stderr)
        return 1

    print("OK: headers de segurança presentes nos nginx de borda.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
