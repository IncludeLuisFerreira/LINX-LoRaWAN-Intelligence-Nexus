#!/usr/bin/env python3
"""Testes negativos da guarda de headers (fixtures temporárias)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "check_security_headers.py"
FILES = ("deploy/nginx/nginx.conf", "client/frontend/nginx.conf")


def run_guard(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def fresh_root() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    for relative in FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return temp


def expect_fail(root: Path, label: str) -> None:
    result = run_guard(root)
    if result.returncode == 0:
        raise AssertionError(f"guarda deveria falhar: {label}")
    print(f"OK (falha esperada): {label}")


def main() -> int:
    with fresh_root() as temp:
        root = Path(temp)
        result = run_guard(root)
        assert result.returncode == 0, result.stderr

        deploy = root / "deploy/nginx/nginx.conf"
        original = deploy.read_text()
        deploy.write_text(
            original.replace(
                '    add_header Content-Security-Policy "default-src '
                "'none'; frame-ancestors 'none'; base-uri 'none'\" "
                "always;\n",
                "",
                1,
            )
        )
        expect_fail(root, "CSP removida de um server do deploy")
        deploy.write_text(original)

        frontend = root / "client/frontend/nginx.conf"
        original = frontend.read_text()
        frontend.write_text(
            original.replace(
                '    add_header X-Content-Type-Options "nosniff" always;\n',
                '    add_header Strict-Transport-Security "max-age=1" always;\n'
                '    add_header X-Content-Type-Options "nosniff" always;\n',
                1,
            )
        )
        expect_fail(root, "HSTS emitido pelo frontend HTTP-only")
        frontend.write_text(original)

        assets_start = original.index("location /assets/")
        assets_end = original.index("location = /mockServiceWorker.js")
        assets = original[assets_start:assets_end].replace(
            "add_header Content-Security-Policy", "# add_header Content-Security-Policy"
        )
        frontend.write_text(
            original[:assets_start] + assets + original[assets_end:]
        )
        expect_fail(root, "CSP ausente na location /assets/")
        frontend.write_text(original)

        first_csp = original.index("add_header Content-Security-Policy")
        frontend.write_text(
            original[:first_csp]
            + "# "
            + original[first_csp:]
        )
        expect_fail(root, "CSP server-level comentada, mas presente em location")
        frontend.write_text(original)

    print("OK: guarda de headers rejeita as fixtures negativas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
