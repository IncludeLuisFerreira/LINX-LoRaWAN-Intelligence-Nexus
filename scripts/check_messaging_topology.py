#!/usr/bin/env python3
"""Guarda estática da topologia de mensageria.

Regras verificadas:
1. Existe exatamente uma definição de broker RabbitMQ nos compose.
2. Essa definição está em ``infra/docker-compose.base.yml``.
3. O stack base declara a rede ``linx-network`` como externa e com nome
   parametrizável por ``LINX_NETWORK``.
4. Compose fora do base não usam credenciais ``RABBITMQ_DEFAULT_*``.

A ferramenta não sobe containers: lê os arquivos ``docker-compose*.yml``
de forma tolerante aos tags do Docker Compose (``!override``, ``!reset``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

BASE_COMPOSE = Path("infra/docker-compose.base.yml")
SCAN_DIRS = ("infra", "linx_core", "deploy", "client", "tests")
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
NETWORK = "linx-network"
EXPECTED_NETWORK_NAME = "${LINX_NETWORK:-linx-network}"


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader que aceita os tags customizados do Docker Compose."""


def _ignore_unknown_tag(loader: yaml.SafeLoader, node: yaml.Node) -> None:
    """Retorna ``None`` para tags desconhecidos (``!override``, ``!reset``)."""
    return None


# ``None`` registra um construtor fallback para qualquer tag não mapeado.
ComposeLoader.add_constructor(None, _ignore_unknown_tag)


def repo_root() -> Path:
    """Raiz do repositório, calculada a partir deste arquivo."""
    return Path(__file__).resolve().parents[1]


def compose_files(root: Path) -> list[Path]:
    """Arquivos compose relevantes, sem duplicatas e sem diretórios ignorados."""
    found: set[Path] = set()
    for name in SCAN_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        for pattern in ("docker-compose*.yml", "docker-compose*.yaml"):
            for path in directory.rglob(pattern):
                if SKIP_DIRS.intersection(path.parts):
                    continue
                found.add(path)
    return sorted(found)


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = yaml.load(file, Loader=ComposeLoader) or {}
    if not isinstance(data, dict):
        raise ValueError("a raiz do compose não é um mapa YAML")
    return data


def _services(path: Path) -> dict[str, Any]:
    services = _load(path).get("services") or {}
    return services if isinstance(services, dict) else {}


def rabbitmq_definitions(root: Path) -> list[Path]:
    """Compose que declaram um serviço com imagem ``rabbitmq:*``."""
    definitions: list[Path] = []
    for path in compose_files(root):
        for config in _services(path).values():
            if not isinstance(config, dict):
                continue
            image = config.get("image")
            if isinstance(image, str) and image.strip().startswith("rabbitmq:"):
                definitions.append(path)
                break
    return definitions


def _validate_network(base: Path) -> list[str]:
    if not base.is_file():
        return [f"rabbitmq_base_ausente: {BASE_COMPOSE} não existe"]

    data = _load(base)
    networks = data.get("networks") or {}
    network = networks.get(NETWORK) if isinstance(networks, dict) else None
    if not isinstance(network, dict):
        return [
            f"rabbitmq_rede_invalida: {BASE_COMPOSE} não declara {NETWORK}"
        ]
    if network.get("external") is not True:
        return [
            f"rabbitmq_rede_invalida: {BASE_COMPOSE} precisa de "
            f"{NETWORK}.external: true"
        ]
    if network.get("name") != EXPECTED_NETWORK_NAME:
        return [
            f"rabbitmq_rede_invalida: {BASE_COMPOSE} precisa de "
            f"{NETWORK}.name: {EXPECTED_NETWORK_NAME}"
        ]
    return []


def _validate_credentials(root: Path, base: Path) -> list[str]:
    violations: list[str] = []
    for path in compose_files(root):
        if path.resolve() == base.resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"compose_invalido: {path}: {exc}")
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if "RABBITMQ_DEFAULT_" in line:
                relative = path.relative_to(root)
                violations.append(
                    f"rabbitmq_credencial_default: {relative}:{lineno} "
                    "use RABBITMQ_ADMIN_USER/RABBITMQ_ADMIN_PASSWORD"
                )
    return violations


def validate(root: Path) -> list[str]:
    """Retorna a lista de violações; lista vazia significa topologia válida."""
    root = Path(root)
    base = root / BASE_COMPOSE

    try:
        definitions = rabbitmq_definitions(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"compose_invalido: {exc}"]

    violations: list[str] = []
    if len(definitions) != 1:
        listing = ", ".join(str(path.relative_to(root)) for path in definitions)
        violations.append(
            "rabbitmq_duplicata: esperado 1 broker, encontrado "
            f"{len(definitions)} ({listing or 'nenhum'})"
        )
    elif definitions[0].resolve() != base.resolve():
        violations.append(
            "rabbitmq_not_in_base: "
            f"{definitions[0].relative_to(root)} (mova para {BASE_COMPOSE})"
        )

    try:
        violations.extend(_validate_network(base))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        violations.append(f"compose_invalido: {BASE_COMPOSE}: {exc}")

    violations.extend(_validate_credentials(root, base))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica se existe um único broker RabbitMQ no stack base."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=repo_root(),
        help="raiz do repositório (default: raiz deste script)",
    )
    args = parser.parse_args(argv)

    violations = validate(args.root)
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
