"""Casos negativos do TLS obrigatório no Mosquitto (issue #81).

Todos os probes rodam dentro do container do broker (`docker compose exec`),
usando o mesmo `mosquitto_pub` dos testes de ACL. Cada caso negativo tem um
controle positivo com o CA correto para provar que a recusa não é apenas
"broker fora do ar".
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from conftest import (
    APP_ID,
    MQTT_PUB_PASS,
    MQTT_PUB_USER,
    MQTT_TLS_ARGS,
    compose_infra,
)

pytestmark = pytest.mark.integration

TOPIC = f"application/{APP_ID}/device/tlsprobe/event/up"


def _publish(host: str, *extra: str) -> Any:
    """Publica via mosquitto_pub dentro do container do broker."""
    return compose_infra(
        "exec",
        "-T",
        "mosquitto",
        "mosquitto_pub",
        "-h",
        host,
        *extra,
        "-u",
        MQTT_PUB_USER,
        "-P",
        MQTT_PUB_PASS,
        "-t",
        TOPIC,
        "-m",
        "tls-probe",
        check=False,
    )


@pytest.fixture
def untrusted_ca(tmp_path: Path) -> str:
    """Gera uma CA auto-signed e a copia para /tmp do container do broker."""
    key = tmp_path / "untrusted.key"
    cert = tmp_path / "untrusted.crt"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=untrusted-ca",
        ],
        check=True,
        capture_output=True,
    )
    compose_infra(
        "exec",
        "-T",
        "mosquitto",
        "sh",
        "-c",
        "cat > /tmp/untrusted-ca.crt",
        input=cert.read_text(),
        check=True,
    )
    return "/tmp/untrusted-ca.crt"


def test_plaintext_1883_is_rejected() -> None:
    """Nao existe listener plaintext: 1883 recusa a conexao (#81)."""
    plaintext = _publish("localhost", "-p", "1883")
    tls = _publish("localhost", *MQTT_TLS_ARGS)

    assert (
        plaintext.returncode != 0
    ), "o listener plaintext 1883 aceitou conexao"
    assert tls.returncode == 0, "controle TLS na 8883 falhou"


def test_untrusted_ca_is_rejected(untrusted_ca: str) -> None:
    """Certificado assinado por outra CA nao e aceito na 8883."""
    wrong = _publish("localhost", "-p", "8883", "--cafile", untrusted_ca)
    trusted = _publish("localhost", *MQTT_TLS_ARGS)

    assert wrong.returncode != 0, "CA nao confiavel foi aceita pelo broker"
    assert trusted.returncode == 0, "controle com a CA correta falhou"


def test_hostname_outside_san_is_rejected() -> None:
    """O SAN so cobre localhost/mosquitto/127.0.0.1 (#81)."""
    correct = _publish("localhost", *MQTT_TLS_ARGS)
    wrong = _publish("127.0.0.2", *MQTT_TLS_ARGS)

    assert correct.returncode == 0, "controle com hostname valido falhou"
    assert wrong.returncode != 0, "hostname fora do SAN foi aceito"
