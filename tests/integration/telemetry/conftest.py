"""Fixtures dos testes de integração de telemetria ponta-a-ponta.

NÃO define uma stack própria: sobe a stack real de `deploy/docker-compose.yml`
em `tests/integration/telemetry/docker-compose.override.yml` (apenas portas de
teste, APP_ID e credencial administrativa do broker), com um `--env-file` de
teste. Sobe só os serviços do caminho da telemetria:

    mosquitto -> routing -> rabbitmq -> telemetry_consumer -> timescaledb

Valida que os containers estão no ar antes dos testes e derruba tudo no fim.
Em falha de subida, imprime o estado de cada serviço e a dica de logs.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx
import pytest
import rabbitpy
from websockets.sync.client import connect as ws_connect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BASE_COMPOSE = os.path.join(ROOT, "deploy", "docker-compose.yml")
OVERRIDE_COMPOSE = os.path.join(HERE, "docker-compose.override.yml")
TEST_ENV_FILE = os.path.join(HERE, "test.env")

PROJECT = "lynx-integration"
SERVICES = (
    "mosquitto",
    "rabbitmq",
    "timescaledb",
    "telemetry_consumer",
    "routing",
)

CONSUMER_HTTP = os.environ.get("IT_CONSUMER_HTTP", "http://127.0.0.1:8011")


def _read_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


_ENV = _read_env(TEST_ENV_FILE)

APP_ID = _ENV.get("APP_ID", "integration-app")
AMQP_URL = os.environ.get("IT_AMQP_URL") or (
    f"amqp://{_ENV.get('RABBITMQ_DEFAULT_USER', 'linx')}:"
    f"{_ENV.get('RABBITMQ_DEFAULT_PASS', 'changeme')}@127.0.0.1:5673/%2f"
)
DB_USER = _ENV.get("DB_USER", "tenant")
DB_NAME = _ENV.get("DB_NAME", "tenantdb")

UP_TIMEOUT = os.environ.get("IT_UP_TIMEOUT", "300")


def _ensure_deploy_env() -> None:
    """Garante `deploy/.env` (exigido por `env_file` do compose base).

    O arquivo é gitignored; no CI ele não existe. Criamos a partir do
    `.env.example` apenas quando ausente — a interpolação real vem do
    `--env-file` de teste, então o conteúdo não afeta as credenciais do teste.
    """
    deploy_env = os.path.join(ROOT, "deploy", ".env")
    if not os.path.exists(deploy_env):
        example = os.path.join(ROOT, "deploy", ".env.example")
        shutil.copyfile(example, deploy_env)


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Executa `docker compose` sobre a stack real (deploy + override)."""
    return subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            PROJECT,
            "--env-file",
            TEST_ENV_FILE,
            "-f",
            BASE_COMPOSE,
            "-f",
            OVERRIDE_COMPOSE,
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
    )


def _services_state() -> dict[str, dict[str, Any]]:
    """Retorna {serviço: {state, health, name}} a partir de `compose ps`."""
    result = compose("ps", "-a", "--format", "json", check=False)
    services: dict[str, dict[str, Any]] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        service = item.get("Service")
        if service:
            services[service] = {
                "state": (item.get("State") or "").lower(),
                "health": (item.get("Health") or "").lower(),
                "name": item.get("Name", service),
            }
    return services


def _is_up(info: dict[str, Any]) -> bool:
    if info["state"] != "running":
        return False
    if info["health"] and info["health"] != "healthy":
        return False
    return True


def _preflight() -> None:
    """Aborta com mensagem clara se algum serviço não estiver no ar."""
    states = _services_state()
    down = [
        (name, states.get(name))
        for name in SERVICES
        if name not in states or not _is_up(states[name])
    ]
    if not down:
        return

    lines = ["", "✗ Serviços da stack de integração fora do ar:"]
    for name, info in down:
        if info is None:
            lines.append(f"  - {name}: não encontrado no `compose ps`")
        else:
            lines.append(
                f"  - {name} ({info['name']}): "
                f"state={info['state'] or '?'} health={info['health'] or '-'}"
            )
    lines.append("")
    lines.append(
        "Veja os logs: docker compose -p lynx-integration "
        f"--env-file {TEST_ENV_FILE} -f {BASE_COMPOSE} -f {OVERRIDE_COMPOSE} "
        "logs <serviço>"
    )
    lines.append("")
    raise RuntimeError("\n".join(lines))


def _dump_logs(focus: Iterator[str]) -> None:
    for name in focus:
        result = compose("logs", "--tail", "40", name, check=False)
        print(f"\n----- logs: {name} -----")
        print(result.stdout or result.stderr)


@pytest.fixture(scope="session", autouse=True)
def stack() -> Iterator[None]:
    """Sobe a stack real (via deploy compose), valida e derruba no fim."""
    _ensure_deploy_env()
    up = compose(
        "up",
        "-d",
        "--build",
        "--wait",
        "--wait-timeout",
        UP_TIMEOUT,
        *SERVICES,
    )
    if up.returncode != 0:
        print(up.stdout)
        print(up.stderr)
        with contextlib.suppress(RuntimeError):
            _preflight()
        _dump_logs(iter(("telemetry_consumer", "routing", "rabbitmq")))
        pytest.exit("falha ao subir a stack de integração", returncode=1)

    try:
        _preflight()
        _wait_consumer()
        _wait_pipeline()
        yield
    finally:
        compose("down", "-v", "--remove-orphans", check=False)


def _wait_consumer(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{CONSUMER_HTTP}/health", timeout=2)
            if response.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(0.5)
    _preflight()
    raise RuntimeError(f"telemetry_consumer não respondeu em {timeout}s ({last})")


def _publish_probe(dev: str) -> None:
    payload = json.dumps(
        {
            "deviceInfo": {"devEui": dev, "applicationId": APP_ID},
            "object": {"temperature": 1.0},
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "rxInfo": [{"rssi": -1, "snr": 0.0}],
        }
    )
    compose(
        "exec",
        "-T",
        "mosquitto",
        "mosquitto_pub",
        "-h",
        "localhost",
        "-t",
        f"application/{APP_ID}/device/{dev}/event/up",
        "-m",
        payload,
        check=False,
    )


def _db_count(dev: str) -> str:
    result = compose(
        "exec",
        "-T",
        "timescaledb",
        "psql",
        "-U",
        DB_USER,
        "-d",
        DB_NAME,
        "-tAc",
        f"select count(*) from telemetry where app_id='{APP_ID}' and dev_eui='{dev}'",
        check=False,
    )
    return result.stdout.strip()


def _wait_pipeline(timeout: float = 60.0) -> None:
    """Prontidão funcional: MQTT -> routing -> rabbitmq -> consumer -> DB.

    `routing` não expõe healthcheck HTTP; publicar um uplink de probe e
    aguardar a linha no banco garante que toda a cadeia está assinando e
    persistindo antes dos testes.
    """
    dev = "70b3d57edfffffff"
    deadline = time.time() + timeout
    while time.time() < deadline:
        _publish_probe(dev)
        time.sleep(1.5)
        if _db_count(dev) not in ("", "0"):
            return
    _preflight()
    _dump_logs(iter(("routing", "telemetry_consumer")))
    raise RuntimeError(
        "pipeline de telemetria não ficou pronto em "
        f"{timeout}s (MQTT -> routing -> rabbitmq -> consumer -> DB)"
    )


# --------------------------------------------------------------------------
# Helpers expostos como fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def publish_amqp() -> Any:
    """Publica um envelope diretamente na exchange do tenant (via AMQP)."""

    def _publish(
        envelope: dict[str, Any], dev_eui: str | None = None, event_type: str = "up"
    ) -> bool:
        dev = dev_eui or envelope["dev_eui"]
        routing_key = f"application.{APP_ID}.device.{dev}.{event_type}"
        connection = rabbitpy.Connection(AMQP_URL)
        try:
            channel = connection.channel()
            channel.enable_publisher_confirms()
            exchange = rabbitpy.Exchange(
                channel,
                f"linx.telemetry.{APP_ID}",
                exchange_type="topic",
                durable=True,
            )
            exchange.declare()
            message = rabbitpy.Message(
                channel,
                json.dumps(envelope).encode(),
                properties={
                    "content_type": "application/json",
                    "delivery_mode": 2,
                },
            )
            return bool(message.publish(exchange, routing_key))
        finally:
            connection.close()

    return _publish


@pytest.fixture
def publish_mqtt() -> Any:
    """Publica um uplink MQTT no mosquitto (mesmo caminho do gateway real)."""

    def _publish(topic: str, payload: dict[str, Any]) -> None:
        result = compose(
            "exec",
            "-T",
            "mosquitto",
            "mosquitto_pub",
            "-h",
            "localhost",
            "-t",
            topic,
            "-m",
            json.dumps(payload),
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "mosquitto_pub falhou: " + (result.stderr or result.stdout)
            )

    return _publish


@pytest.fixture
def ws_open() -> Any:
    """Abre uma conexão WS (context manager) para medir latência."""

    def _open(timeout: float = 10.0) -> Any:
        url = f"{CONSUMER_HTTP.replace('http', 'ws')}/ws/telemetry/{APP_ID}"
        return ws_connect(url, open_timeout=timeout)

    return _open


@pytest.fixture
def db_scalar() -> Any:
    """Executa um SELECT no TimescaleDB e retorna o valor escalar."""

    def _scalar(sql: str) -> str:
        result = compose(
            "exec",
            "-T",
            "timescaledb",
            "psql",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-tAc",
            sql,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("psql falhou: " + (result.stderr or result.stdout))
        return result.stdout.strip()

    return _scalar


@pytest.fixture
def rest_get() -> Any:
    def _get(path: str) -> Any:
        return httpx.get(f"{CONSUMER_HTTP}{path}", timeout=10)

    return _get
