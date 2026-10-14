"""Testes de integração ponta-a-ponta da telemetria (issue #43).

Cobrem o caminho real — mosquitto -> routing -> rabbitmq -> telemetry_consumer
-> TimescaleDB + broadcast WebSocket — e os dois contratos que o dashboard
consome: `GET /telemetry` (histórico) e `WS /ws/telemetry/{app_id}` (tempo real).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

import pytest

from conftest import APP_ID

pytestmark = pytest.mark.integration


def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def wait_until(
    predicate: Callable[[], bool], timeout: float = 15.0, step: float = 0.5
) -> bool:
    """Poll `predicate` até o prazo. `time.sleep` fixo é flaky no hop extra
    dead-letter + métrica da API de gestão."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return bool(predicate())


def recv_matching(
    ws: Any, predicate: Callable[[dict[str, Any]], bool], timeout: float = 10.0
) -> dict[str, Any]:
    import json

    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError(
                f"WS não recebeu mensagem esperada em {timeout}s"
            )
        message = json.loads(ws.recv(timeout=remaining))
        if predicate(message):
            return message


def envelope(dev_eui: str, ts: str, temperature: float = 23.5) -> dict[str, Any]:
    return {
        "app_id": APP_ID,
        "dev_eui": dev_eui,
        "event_type": "up",
        "payload": {"temperature": temperature, "humidity": 61},
        "timestamp": ts,
        "rssi": -72,
        "snr": 7.5,
    }


def test_uplink_mqtt_reaches_frontend_contracts(
    publish_mqtt: Any, ws_open: Any, rest_get: Any, db_count: Any
) -> None:
    """Uplink MQTT (gateway) chega ao WS e ao REST do frontend em <= 2s."""
    dev = "70b3d57ed0000aaa"
    ts = now_iso()

    with ws_open() as ws:
        started = time.time()
        publish_mqtt(
            f"application/{APP_ID}/device/{dev}/event/up",
            {
                "deviceInfo": {"devEui": dev, "applicationId": APP_ID},
                "object": {"temperature": 23.5, "humidity": 61},
                "time": ts,
                "rxInfo": [{"rssi": -72, "snr": 7.5}],
            },
        )
        message = recv_matching(
            ws, lambda m: m["dev_eui"] == dev and m["time"] == ts
        )
        latency = time.time() - started

    assert latency <= 2.0, f"latência {latency:.3f}s acima de 2s (RNF-003)"
    assert message["app_id"] == APP_ID
    assert message["payload"]["temperature"] == 23.5

    items = rest_get(f"/telemetry?dev_eui={dev}&limit=10").json()["items"]
    assert any(item["dev_eui"] == dev for item in items), "REST não retornou o ponto"

    assert db_count(dev) == "1"


def test_amqp_envelope_persisted_and_broadcast(
    publish_amqp: Any, ws_open: Any, rest_get: Any, db_count: Any
) -> None:
    """Envelope AMQP válido persiste e é difundido no WebSocket."""
    dev = "70b3d57ed0000bbb"
    ts = now_iso()

    with ws_open() as ws:
        assert publish_amqp(envelope(dev, ts))
        message = recv_matching(
            ws, lambda m: m["dev_eui"] == dev and m["time"] == ts
        )

    assert message["event_type"] == "up"
    assert db_count(dev) == "1"
    items = rest_get(f"/telemetry?dev_eui={dev}&limit=10").json()["items"]
    assert any(item["dev_eui"] == dev for item in items)


def test_duplicate_envelope_is_idempotent(
    publish_amqp: Any, db_count: Any
) -> None:
    """Reenvio do mesmo (app_id, dev_eui, time, event_type) não duplica."""
    dev = "70b3d57ed0000ccc"
    ts = now_iso()

    assert publish_amqp(envelope(dev, ts))
    assert publish_amqp(envelope(dev, ts))

    time.sleep(2)
    assert db_count(dev) == "1"


def test_invalid_envelope_is_not_persisted(
    publish_amqp: Any, db_count: Any, dlq_messages: Any
) -> None:
    """Envelope sem `payload` vai para a DLQ, sem persistir.

    Estreita o contrato prometido no README: nao basta "nao aparecer no banco"
    -- o corpo bruto precisa chegar de fato na fila de dead-letter do tenant.
    """
    dev = "70b3d57ed0000ddd"
    ts = now_iso()
    bad = {
        "app_id": APP_ID,
        "dev_eui": dev,
        "event_type": "up",
        "timestamp": ts,
    }

    before = dlq_messages()

    assert publish_amqp(bad)

    assert wait_until(lambda: dlq_messages() >= before + 1), (
        "payload inválido não chegou à DLQ em 15s"
    )
    assert db_count(dev) == "0"


def test_iso_string_timestamp_regression(
    publish_amqp: Any, rest_get: Any, db_count: Any
) -> None:
    """Regressão: `timestamp` string ISO precisa ser aceito pelo consumer.

    O caminho real entrega o timestamp como string; o asyncpg exige datetime
    no parâmetro `$1::timestamptz`. Sem a coerção, todo uplink falharia.
    """
    dev = "70b3d57ed0000eee"
    ts = now_iso()
    assert isinstance(ts, str)

    assert publish_amqp(envelope(dev, ts))
    time.sleep(2)

    assert db_count(dev) == "1"
    items = rest_get(f"/telemetry?dev_eui={dev}&limit=10").json()["items"]
    assert len(items) == 1
