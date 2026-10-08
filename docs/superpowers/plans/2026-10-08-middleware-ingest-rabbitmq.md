# Middleware ingest MQTT → RabbitMQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar `middleware/services/routing` em um serviço de ingestão que consome a telemetria do ChirpStack via MQTT, valida a integridade da mensagem e publica um envelope normalizado em um exchange `topic` do RabbitMQ.

**Architecture:** Um único serviço com módulos separados por responsabilidade (`config`, `validation`, `envelope`, `publisher`, `consumer`) orquestrados por `routing.py`. O consumer paho valida na thread de callback e enfileira uplinks válidos; uma única thread publisher (rabbitpy, publisher confirms) drena a fila e publica. O roteamento para consumidores finais é feito por filas e bindings no RabbitMQ.

**Tech Stack:** Python 3.12, paho-mqtt 2.x, rabbitpy 3.x, pydantic-settings, pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-middleware-ingest-rabbitmq-design.md`

## Global Constraints

- Python `>=3.12,<4.0`; `black` line-length `79`; `isort` profile `black`, line-length 79.
- Cobertura de testes `>= 70%` (`pytest --cov=src --cov-fail-under=70`).
- Exchange `topic` durável, nome default `linx.telemetry`.
- Mensagens persistentes: propriedades `content_type=application/json`, `delivery_mode=2`.
- Routing key: `application.{app_id}.device.{dev_eui}.{event_type}`.
- Tópico MQTT consumido: `application/+/device/+/event/up`; QoS `1`.
- Envelope publicado (JSON): `{app_id, dev_eui, event_type, payload, rssi?, snr?, timestamp}`.
- Validação descarta com `warning` e nunca lança para fora do callback.
- Defaults de código apontam para `localhost`; o compose sobrescreve com nomes de serviço.
- Sem `httpx`, `sqlalchemy`, `psycopg` no serviço ao final; sem `device_routes`/`DATABASE_URL`.

## Review Focus

Estes são os modos de falha prováveis que a spec implica; cada um ganha teste na tarefa dona.

1. Tópico com número errado de segmentos, prefixo/sufixo errado, ou `/` extra → `parse_topic` retorna `None` e a mensagem é descartada (Task 2).
2. `event["object"]` presente mas não é objeto (ex.: string) ou ausente → descartado (Task 2).
3. `rxInfo` ausente, lista vazia, ou item sem `rssi`/`snr` → envelope sem essas chaves (Task 3).
4. Bytes não-UTF8 ou JSON inválido → descartado, `loop` MQTT não quebra (Task 2, Task 5).
5. RabbitMQ indisponível na partida ou `publish` retorna `False` → retry com backoff e depois descarte; serviço não cai (Task 4, Task 6).

---

### Task 1: Configuração e dependência rabbitpy

**Files:**
- Modify: `middleware/services/routing/pyproject.toml`
- Modify: `middleware/services/routing/src/routing/config.py`
- Test: `middleware/services/routing/tests/test_config.py`

**Interfaces:**
- Produces: `RoutingSettings` com campos `mqtt_broker_host: str = "localhost"`, `mqtt_broker_port: int = 1883`, `mqtt_topic: str = "application/+/device/+/event/up"`, `mqtt_qos: int = 1`, `rabbit_url: str = "amqp://guest:guest@localhost:5672/%2f"`, `rabbit_exchange: str = "linx.telemetry"`, `max_payload_bytes: int = 65536`, `rabbit_connect_max_attempts: int = 5`, `rabbit_connect_backoff_seconds: float = 1.0`.

- [ ] **Step 1: Write the failing test**

Substituir `tests/test_config.py` por:

```python
from routing.config import RoutingSettings


def test_settings_defaults(monkeypatch):
    for var in (
        "MQTT_BROKER_HOST",
        "MQTT_BROKER_PORT",
        "MQTT_TOPIC",
        "MQTT_QOS",
        "RABBIT_URL",
        "RABBIT_EXCHANGE",
        "MAX_PAYLOAD_BYTES",
        "RABBIT_CONNECT_MAX_ATTEMPTS",
        "RABBIT_CONNECT_BACKOFF_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = RoutingSettings(_env_file=None)

    assert settings.mqtt_broker_host == "localhost"
    assert settings.mqtt_broker_port == 1883
    assert settings.mqtt_topic == "application/+/device/+/event/up"
    assert settings.mqtt_qos == 1
    assert settings.rabbit_url == "amqp://guest:guest@localhost:5672/%2f"
    assert settings.rabbit_exchange == "linx.telemetry"
    assert settings.max_payload_bytes == 65536
    assert settings.rabbit_connect_max_attempts == 5
    assert settings.rabbit_connect_backoff_seconds == 1.0


def test_settings_override(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_BROKER_PORT", "8883")
    monkeypatch.setenv("MQTT_QOS", "0")
    monkeypatch.setenv("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/%2f")
    monkeypatch.setenv("RABBIT_EXCHANGE", "custom.telemetry")
    monkeypatch.setenv("MAX_PAYLOAD_BYTES", "1024")

    settings = RoutingSettings(_env_file=None)

    assert settings.mqtt_broker_host == "broker.example.com"
    assert settings.mqtt_broker_port == 8883
    assert settings.mqtt_qos == 0
    assert settings.rabbit_url == "amqp://guest:guest@rabbitmq:5672/%2f"
    assert settings.rabbit_exchange == "custom.telemetry"
    assert settings.max_payload_bytes == 1024
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_config.py -v`
Expected: FAIL — `AttributeError`/`ValidationError` para `mqtt_qos`/`rabbit_url`.

- [ ] **Step 3: Add rabbitpy dependency and update config**

Em `pyproject.toml`, na seção `[tool.poetry.dependencies]`, adicionar (manter as demais por enquanto):

```toml
rabbitpy = ">=3.0,<4.0"
```

Substituir `src/routing/config.py` por:

```python
from linx_shared.core.config import Settings


class RoutingSettings(Settings):
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "application/+/device/+/event/up"
    mqtt_qos: int = 1
    rabbit_url: str = "amqp://guest:guest@localhost:5672/%2f"
    rabbit_exchange: str = "linx.telemetry"
    max_payload_bytes: int = 65536
    rabbit_connect_max_attempts: int = 5
    rabbit_connect_backoff_seconds: float = 1.0


settings = RoutingSettings()
```

Run: `cd middleware && poetry -C services/routing install` para materializar `rabbitpy`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/services/routing/pyproject.toml middleware/services/routing/poetry.lock middleware/services/routing/src/routing/config.py middleware/services/routing/tests/test_config.py
git commit -m "feat(middleware): adiciona config RabbitMQ e dependência rabbitpy"
```

---

### Task 2: Módulo de validação de integridade

**Files:**
- Create: `middleware/services/routing/src/routing/validation.py`
- Test: `middleware/services/routing/tests/test_validation.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) TopicParts` com `app_id: str`, `dev_eui: str`, `event_type: str`.
  - `@dataclass(frozen=True) ValidUplink` com `app_id: str`, `dev_eui: str`, `event_type: str`, `event: dict[str, Any]`.
  - `parse_topic(topic: str) -> TopicParts | None`.
  - `validate_message(topic: str, raw: bytes, max_bytes: int) -> ValidUplink | None`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_validation.py`:

```python
import json

from routing.validation import TopicParts, parse_topic, validate_message


def _raw(event: dict) -> bytes:
    return json.dumps(event).encode()


_VALID = {"object": {"t": 20}, "time": "2026-10-08T12:00:00Z"}
_TOPIC = "application/app1/device/devA/event/up"


def test_parse_topic_valid():
    assert parse_topic(_TOPIC) == TopicParts("app1", "devA", "up")


def test_parse_topic_rejects_bad_segments():
    assert parse_topic("other/app1/device/devA/event/up") is None
    assert parse_topic("application/app1/other/devA/event/up") is None
    assert parse_topic("application/app1/device/devA/other/up") is None
    assert parse_topic("application/app1/device/devA/event") is None
    assert parse_topic("application/app1/device/devA/event/up/extra") is None
    assert parse_topic("") is None


def test_validate_message_ok():
    uplink = validate_message(_TOPIC, _raw(_VALID), max_bytes=65536)

    assert uplink is not None
    assert uplink.app_id == "app1"
    assert uplink.dev_eui == "devA"
    assert uplink.event_type == "up"
    assert uplink.event == _VALID


def test_validate_message_drops_oversize(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"x" * 11, max_bytes=10) is None
    assert "payload" in caplog.text


def test_validate_message_accepts_exactly_at_limit():
    raw = _raw(_VALID)
    assert validate_message(_TOPIC, raw, max_bytes=len(raw)) is not None


def test_validate_message_drops_invalid_json(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"not-json", max_bytes=65536) is None
    assert "inválido" in caplog.text


def test_validate_message_drops_non_utf8(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"\xff\xfe", max_bytes=65536) is None


def test_validate_message_drops_non_object_json(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, b"[1, 2]", max_bytes=65536) is None


def test_validate_message_drops_bad_topic():
    assert validate_message("weird/topic", _raw(_VALID), max_bytes=65536) is None


def test_validate_message_drops_missing_object(caplog):
    with caplog.at_level("WARNING"):
        assert validate_message(_TOPIC, _raw({"time": "t"}), max_bytes=65536) is None


def test_validate_message_drops_non_dict_object(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(
                _TOPIC, _raw({"object": "x", "time": "t"}), max_bytes=65536
            )
            is None
        )


def test_validate_message_drops_missing_timestamp(caplog):
    with caplog.at_level("WARNING"):
        assert (
            validate_message(_TOPIC, _raw({"object": {}}), max_bytes=65536)
            is None
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: routing.validation`.

- [ ] **Step 3: Implement `validation.py`**

Assinaturas exatas: `parse_topic(topic: str) -> TopicParts | None`; `validate_message(topic: str, raw: bytes, max_bytes: int) -> ValidUplink | None`. Ordem da validação (cada falha loga `warning` e retorna `None`): tamanho do payload → `parse_topic` → `json.loads(raw.decode())` (capturar `JSONDecodeError` e `UnicodeDecodeError`) → é `dict` → `object` é `dict` → `time` presente. Use `logger = logging.getLogger(__name__)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/services/routing/src/routing/validation.py middleware/services/routing/tests/test_validation.py
git commit -m "feat(middleware): valida integridade do uplink MQTT"
```

---

### Task 3: Módulo de envelope e routing key

**Files:**
- Create: `middleware/services/routing/src/routing/envelope.py`
- Test: `middleware/services/routing/tests/test_envelope.py`

**Interfaces:**
- Consumes: `ValidUplink` de `routing.validation` (Task 2).
- Produces: `build_envelope(uplink: ValidUplink) -> dict[str, Any]`; `routing_key(app_id: str, dev_eui: str, event_type: str) -> str`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_envelope.py`:

```python
from routing.envelope import build_envelope, routing_key
from routing.validation import ValidUplink


def _uplink(event):
    return ValidUplink(app_id="app1", dev_eui="devA", event_type="up", event=event)


def test_routing_key_format():
    assert (
        routing_key("app1", "devA", "up")
        == "application.app1.device.devA.up"
    )


def test_build_envelope_with_radio():
    event = {
        "object": {"t": 20},
        "rxInfo": [{"rssi": -60, "snr": 7.5}],
        "time": "2026-10-08T12:00:00Z",
    }

    assert build_envelope(_uplink(event)) == {
        "app_id": "app1",
        "dev_eui": "devA",
        "event_type": "up",
        "payload": {"t": 20},
        "rssi": -60,
        "snr": 7.5,
        "timestamp": "2026-10-08T12:00:00Z",
    }


def test_build_envelope_without_rssi_snr_omits_keys():
    event = {"object": {}, "time": "t"}

    envelope = build_envelope(_uplink(event))

    assert envelope["payload"] == {}
    assert "rssi" not in envelope
    assert "snr" not in envelope


def test_build_envelope_empty_rxinfo_omits_keys():
    event = {"object": {}, "time": "t", "rxInfo": []}

    envelope = build_envelope(_uplink(event))

    assert "rssi" not in envelope
    assert "snr" not in envelope


def test_build_envelope_partial_rxinfo_only_rssi():
    event = {"object": {}, "time": "t", "rxInfo": [{"rssi": -70}]}

    envelope = build_envelope(_uplink(event))

    assert envelope["rssi"] == -70
    assert "snr" not in envelope
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_envelope.py -v`
Expected: FAIL — `ModuleNotFoundError: routing.envelope`.

- [ ] **Step 3: Implement `envelope.py`**

`build_envelope` monta o dict com `app_id`, `dev_eui`, `event_type`, `payload = uplink.event["object"]`, `timestamp = uplink.event["time"]`, e adiciona `rssi`/`snr` somente se `event.get("rxInfo")` for lista não vazia e o primeiro item (dict) contiver a chave. `routing_key(app_id, dev_eui, event_type)` retorna `f"application.{app_id}.device.{dev_eui}.{event_type}"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_envelope.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/services/routing/src/routing/envelope.py middleware/services/routing/tests/test_envelope.py
git commit -m "feat(middleware): monta envelope e routing key do uplink"
```

---

### Task 4: Publisher RabbitMQ

**Files:**
- Create: `middleware/services/routing/src/routing/publisher.py`
- Test: `middleware/services/routing/tests/test_publisher.py`

**Interfaces:**
- Produces: classe `RabbitPublisher` com
  - `__init__(self, url: str, exchange: str, connect_max_attempts: int = 5, backoff_seconds: float = 1.0)`.
  - `connect(self) -> bool` — conecta com retry/backoff, abre channel, `enable_publisher_confirms()`, declara exchange `topic` durável.
  - `publish(self, routing_key: str, body: dict[str, Any]) -> bool` — JSON, `content_type=application/json`, `delivery_mode=2`; retorna `bool`.
  - `close(self) -> None`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_publisher.py`. Injetar um módulo `rabbitpy` falso via `monkeypatch.setattr("routing.publisher.rabbitpy", fake)`.

```python
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from routing import publisher as publisher_module
from routing.publisher import RabbitPublisher


class _FakeRabbit:
    def __init__(self):
        self.connection_calls = []
        self.last_message = None
        self.published = []
        self.exchange = None

    def Connection(self, url):
        self.connection_calls.append(url)
        return self._connection()

    def _connection(self):
        conn = MagicMock()
        channel = MagicMock()
        conn.channel.return_value = channel
        self.channel = channel
        return conn

    def Exchange(self, channel, name, exchange_type="direct", durable=True, auto_delete=False, arguments=None):
        self.exchange = SimpleNamespace(
            name=name, exchange_type=exchange_type, durable=durable
        )
        self.exchange.declare = MagicMock()
        return self.exchange

    def Message(self, channel, body, properties=None):
        self.last_message = SimpleNamespace(
            body=body, properties=properties, publish=MagicMock(return_value=True)
        )
        return self.last_message


@pytest.fixture
def fake_rabbit(monkeypatch):
    fake = _FakeRabbit()
    monkeypatch.setattr(publisher_module, "rabbitpy", fake)
    return fake


def test_connect_declares_durable_topic_exchange(fake_rabbit):
    pub = RabbitPublisher("amqp://h", "linx.telemetry")

    assert pub.connect() is True
    assert fake_rabbit.connection_calls == ["amqp://h"]
    assert fake_rabbit.exchange.name == "linx.telemetry"
    assert fake_rabbit.exchange.exchange_type == "topic"
    assert fake_rabbit.exchange.durable is True
    assert fake_rabbit.channel.enable_publisher_confirms.called


def test_connect_retries_then_succeeds(monkeypatch, fake_rabbit):
    monkeypatch.setattr("routing.publisher.time.sleep", lambda *_: None)
    attempts = {"n": 0}
    real_connection = fake_rabbit.Connection

    def flaky(url):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("offline")
        return real_connection(url)

    fake_rabbit.Connection = flaky
    pub = RabbitPublisher("amqp://h", "linx.telemetry")

    assert pub.connect() is True
    assert attempts["n"] == 3


def test_connect_gives_up_and_returns_false(monkeypatch, fake_rabbit, caplog):
    monkeypatch.setattr("routing.publisher.time.sleep", lambda *_: None)
    fake_rabbit.Connection = MagicMock(side_effect=OSError("offline"))
    pub = RabbitPublisher("amqp://h", "linx.telemetry", connect_max_attempts=2)

    with caplog.at_level("ERROR"):
        assert pub.connect() is False
    assert fake_rabbit.Connection.call_count == 2


def test_publish_sends_persistent_json(fake_rabbit):
    pub = RabbitPublisher("amqp://h", "linx.telemetry")
    pub.connect()

    assert pub.publish("application.app1.device.devA.up", {"a": 1}) is True

    msg = fake_rabbit.last_message
    assert json.loads(msg.body) == {"a": 1}
    assert msg.properties["content_type"] == "application/json"
    assert msg.properties["delivery_mode"] == 2
    msg.publish.assert_called_once_with(
        fake_rabbit.exchange, "application.app1.device.devA.up"
    )


def test_publish_returns_false_when_broker_rejects(fake_rabbit, caplog):
    pub = RabbitPublisher("amqp://h", "linx.telemetry")
    pub.connect()
    fake_rabbit.Message = lambda channel, body, properties=None: SimpleNamespace(
        publish=MagicMock(return_value=False)
    )

    with caplog.at_level("ERROR"):
        assert pub.publish("rk", {"a": 1}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_publisher.py -v`
Expected: FAIL — `ModuleNotFoundError: routing.publisher`.

- [ ] **Step 3: Implement `publisher.py`**

`import rabbitpy` no topo do módulo (para o `monkeypatch` funcionar). `connect` faz o loop de `connect_max_attempts` com `time.sleep(backoff_seconds)` entre tentativas, tratando `Exception` de rede; em sucesso, guarda `self._channel` e `self._exchange`, chama `self._channel.enable_publisher_confirms()` e `self._exchange.declare()`. `publish` serializa o corpo com `json.dumps`, cria `rabbitpy.Message(self._channel, body_bytes, properties={"content_type": "application/json", "delivery_mode": 2})`, chama `message.publish(self._exchange, routing_key)`, loga `error` e retorna `False` quando o retorno não é verdadeiro. `close` fecha a conexão, tolerando exceções.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_publisher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/services/routing/src/routing/publisher.py middleware/services/routing/tests/test_publisher.py
git commit -m "feat(middleware): publica envelope em exchange RabbitMQ com confirms"
```

---

### Task 5: Consumer MQTT

**Files:**
- Create: `middleware/services/routing/src/routing/consumer.py`
- Test: `middleware/services/routing/tests/test_consumer.py`

**Interfaces:**
- Consumes: `validate_message` e `ValidUplink` de `routing.validation` (Task 2).
- Produces: classe `MqttConsumer` com
  - `__init__(self, *, broker_host: str, broker_port: int, topic: str, qos: int, max_payload_bytes: int, out_queue: queue.Queue)`.
  - `on_connect(self, client, userdata, connect_flags, reason_code, properties=None) -> None` — assina o tópico quando `reason_code == 0`.
  - `on_message(self, client, userdata, message) -> None` — valida e enfileira `ValidUplink`; descarta inválidos.
  - `on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None) -> None`.
  - `start(self) -> bool` — cria o `paho.mqtt.client.Client` (VERSION2), registra callbacks, conecta com retry/backoff e chama `loop_forever`.
  - `stop(self) -> None`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_consumer.py`:

```python
import json
import queue
from unittest.mock import MagicMock

import paho.mqtt.client as mqtt

from routing.consumer import MqttConsumer
from routing.validation import ValidUplink


def _consumer():
    q = queue.Queue()
    consumer = MqttConsumer(
        broker_host="h",
        broker_port=1883,
        topic="application/+/device/+/event/up",
        qos=1,
        max_payload_bytes=65536,
        out_queue=q,
    )
    consumer.client = MagicMock()
    return consumer, q


def test_on_connect_subscribes_on_success():
    consumer, _ = _consumer()
    rc = mqtt.convert_connack_rc_to_reason_code(0)

    consumer.on_connect(consumer.client, None, None, rc, None)

    consumer.client.subscribe.assert_called_once_with(consumer.topic, qos=1)


def test_on_connect_failure_does_not_subscribe():
    consumer, _ = _consumer()
    rc = mqtt.convert_connack_rc_to_reason_code(1)

    consumer.on_connect(consumer.client, None, None, rc, None)

    consumer.client.subscribe.assert_not_called()


def test_on_message_enqueues_valid_uplink():
    consumer, q = _consumer()
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = json.dumps(
        {"object": {"t": 20}, "time": "2026-10-08T12:00:00Z"}
    ).encode()

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 1
    uplink = q.get_nowait()
    assert isinstance(uplink, ValidUplink)
    assert uplink.dev_eui == "devA"


def test_on_message_drops_invalid(caplog):
    consumer, q = _consumer()
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = b"not-json"

    with caplog.at_level("WARNING"):
        consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 0


def test_on_message_never_raises(monkeypatch):
    consumer, q = _consumer()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("routing.consumer.validate_message", boom)
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = b"{}"

    consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 0


def test_on_message_drops_when_queue_full(monkeypatch, caplog):
    q = queue.Queue(maxsize=1)
    q.put("occupied")
    consumer = MqttConsumer(
        broker_host="h",
        broker_port=1883,
        topic="application/+/device/+/event/up",
        qos=1,
        max_payload_bytes=65536,
        out_queue=q,
    )
    consumer.client = MagicMock()
    message = MagicMock()
    message.topic = "application/app1/device/devA/event/up"
    message.payload = json.dumps(
        {"object": {}, "time": "t"}
    ).encode()

    with caplog.at_level("ERROR"):
        consumer.on_message(consumer.client, None, message)

    assert q.qsize() == 1


def test_stop_disconnects_and_stops_loop():
    consumer, _ = _consumer()

    consumer.stop()

    consumer.client.disconnect.assert_called_once()
    consumer.client.loop_stop.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_consumer.py -v`
Expected: FAIL — `ModuleNotFoundError: routing.consumer`.

- [ ] **Step 3: Implement `consumer.py`**

`on_message` envolve a validação em `try/except Exception` (loga `exception` e nunca propaga), chama `validate_message(message.topic, message.payload or b"", self.max_payload_bytes)`, e em sucesso faz `self.out_queue.put_nowait(uplink)`; em `queue.Full` loga `error`. `on_connect` assina com `client.subscribe(self.topic, qos=self.qos)` quando `reason_code == 0`. `start` espelha a conectividade atual: `mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)`, registra os três callbacks, `connect` com retry/backoff (reusa as constantes de config) e `loop_forever()`; retorna `False` se esgotar. `stop` desconecta e chama `loop_stop`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_consumer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add middleware/services/routing/src/routing/consumer.py middleware/services/routing/tests/test_consumer.py
git commit -m "feat(middleware): consumer MQTT valida e enfileira uplinks"
```

---

### Task 6: Orquestração do serviço e remoção do caminho HTTP/DB

**Files:**
- Modify: `middleware/services/routing/src/routing/routing.py` (reescrever)
- Modify: `middleware/services/routing/pyproject.toml` (remover `httpx`, `sqlalchemy`, `psycopg`)
- Modify: `middleware/services/routing/tests/test_routing.py` (reescrever)

**Interfaces:**
- Consumes: `MqttConsumer` (Task 5), `RabbitPublisher` (Task 4), `validate_message`/`ValidUplink` (Task 2), `build_envelope`/`routing_key` (Task 3), `settings` (Task 1).
- Produces: classe `IngestService` com `__init__(self)`, `start(self) -> None`, `stop(self) -> None`, `_start_publisher_thread(self) -> None` (spawn da thread daemon que roda `_publisher_worker`), `_publisher_worker(self) -> None`, e função `main() -> None`.

- [ ] **Step 1: Write the failing test**

Substituir `tests/test_routing.py` por (mantém o comportamento de wiring; remove os testes de HTTP/DB/SSRF):

```python
import queue
from unittest.mock import MagicMock

from routing.routing import IngestService
from routing.validation import ValidUplink


def _service():
    service = IngestService()
    service.consumer = MagicMock()
    service.publisher = MagicMock()
    service.publisher.publish.return_value = True
    return service


def test_publisher_worker_drains_queue():
    service = _service()
    seen = []

    def fake_publish(routing_key, body):
        seen.append((routing_key, body))
        service._stop_event.set()
        return True

    service.publisher.publish.side_effect = fake_publish
    service._q.put(
        ValidUplink(
            app_id="app1",
            dev_eui="devA",
            event_type="up",
            event={"object": {"t": 20}, "time": "t"},
        )
    )

    service._publisher_worker()

    assert seen[0][0] == "application.app1.device.devA.up"
    assert seen[0][1]["payload"] == {"t": 20}
    assert service._q.qsize() == 0


def test_publisher_worker_exits_on_sentinel():
    service = _service()
    service._q.put(None)

    service._publisher_worker()

    service.publisher.publish.assert_not_called()


def test_start_connects_publisher_then_starts_thread_then_consumer():
    service = _service()
    order = []
    service.publisher.connect.side_effect = lambda: order.append("connect") or True
    service._start_publisher_thread = lambda: order.append("thread")
    service.consumer.start.side_effect = lambda: order.append("consumer")

    service.start()

    assert order == ["connect", "thread", "consumer"]


def test_start_aborts_when_publisher_cannot_connect():
    service = _service()
    service.publisher.connect.return_value = False
    service._start_publisher_thread = MagicMock()

    service.start()

    service._start_publisher_thread.assert_not_called()
    service.consumer.start.assert_not_called()


def test_stop_stops_consumer_before_closing_publisher():
    service = _service()
    order = []
    service.consumer.stop.side_effect = lambda: order.append("consumer")
    service.publisher.close.side_effect = lambda: order.append("close")

    service.stop()

    assert order == ["consumer", "close"]


def test_wiring_builds_queue_consumer_and_publisher():
    service = IngestService()
    try:
        assert isinstance(service._q, queue.Queue)
        assert service.consumer.qos == 1
        assert service.consumer.out_queue is service._q
        assert service.publisher is not None
    finally:
        service.publisher.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd middleware && poetry -C services/routing run pytest services/routing/tests/test_routing.py -v`
Expected: FAIL — `ImportError: cannot import name 'IngestService'`.

- [ ] **Step 3: Rewrite `routing.py`**

Substituir todo o conteúdo por: `IngestService` que no `__init__` cria `self._q = queue.Queue(maxsize=1000)`, `self._stop_event = threading.Event()`, `self.consumer = MqttConsumer(broker_host=settings.mqtt_broker_host, broker_port=settings.mqtt_broker_port, topic=settings.mqtt_topic, qos=settings.mqtt_qos, max_payload_bytes=settings.max_payload_bytes, out_queue=self._q)` e `self.publisher = RabbitPublisher(settings.rabbit_url, settings.rabbit_exchange, settings.rabbit_connect_max_attempts, settings.rabbit_connect_backoff_seconds)`. `_publisher_worker` faz `get(timeout=1.0)`, encerra em `None`, monta `build_envelope(uplink)`/`routing_key(...)` e chama `publisher.publish`, tratando exceções com `exception`. `start` chama `publisher.connect()` (aborta se `False`), inicia a thread publisher (daemon), e chama `consumer.start()` (bloqueante). `stop` chama `consumer.stop()`, drena a fila com um `None`, junta a thread, fecha o publisher. `main()` configura `logging.basicConfig`, registra `SIGTERM`/`SIGINT` para `service.stop()`, e chama `service.start()`. Manter `if __name__ == "__main__": main()`. Marcar `main()` e a chamada bloqueante `loop_forever` com `# pragma: no cover`, para não derrubar a cobertura.

Remover de `pyproject.toml`: `httpx`, `sqlalchemy`, `psycopg` (e a config mypy de `sqlalchemy` se houver). Rodar `cd middleware && poetry -C services/routing lock`.

- [ ] **Step 4: Run the full package test suite to verify it passes**

Run: `cd middleware && poetry -C services/routing run pytest --cov=src --cov-report=term-missing --cov-fail-under=70 -v`
Expected: PASS, cobertura ≥ 70%.

- [ ] **Step 5: Run lint/typecheck**

Run: `cd middleware && poetry -C services/routing run black --check src tests && poetry -C services/routing run isort --check-only src tests && poetry -C services/routing run flake8 src tests && poetry -C services/routing run mypy src tests`
Expected: sem erros.

- [ ] **Step 6: Commit**

```bash
git add middleware/services/routing/src/routing/routing.py middleware/services/routing/pyproject.toml middleware/services/routing/poetry.lock middleware/services/routing/tests/test_routing.py
git commit -m "refactor(middleware): substitui roteamento HTTP por ingest no RabbitMQ"
```

---

### Task 7: RabbitMQ na stack de deploy

**Files:**
- Modify: `deploy/docker-compose.yml`
- Modify: `deploy/.env.example`

**Interfaces:**
- Consumes: nomes de configuração de Task 1 (`RABBIT_URL`, `RABBIT_EXCHANGE`).
- Produces: service compose `rabbitmq` saudável; `routing` conectado a ele.

- [ ] **Step 1: Add the rabbitmq service**

Em `deploy/docker-compose.yml`, adicionar antes de `routing`:

```yaml
  rabbitmq:
    image: rabbitmq:3-management
    restart: unless-stopped
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
```

Adicionar `rabbitmq_data:` à seção `volumes:`.

- [ ] **Step 2: Point routing at rabbitmq**

No service `routing`, remover a linha `DATABASE_URL` e adicionar:

```yaml
      - RABBIT_URL=${RABBIT_URL:-amqp://guest:guest@rabbitmq:5672/%2f}
      - RABBIT_EXCHANGE=${RABBIT_EXCHANGE:-linx.telemetry}
```

Em `depends_on`, adicionar:

```yaml
      rabbitmq:
        condition: service_healthy
```

- [ ] **Step 3: Document env vars**

Em `deploy/.env.example`, adicionar `RABBIT_URL` e `RABBIT_EXCHANGE` com os defaults acima. Remover `HTTP_TIMEOUT_SECONDS`/`AGENT_ENDPOINT_ALLOWLIST`/`DATABASE_URL` se existirem apenas para o routing.

- [ ] **Step 4: Validate the compose file**

Run: `cd deploy && docker compose config >/dev/null && echo OK`
Expected: `OK` (sem erro de sintaxe/interpolação).

- [ ] **Step 5: Commit**

```bash
git add deploy/docker-compose.yml deploy/.env.example
git commit -m "build(deploy): adiciona RabbitMQ e ajusta routing ao novo ingest"
```

---

### Task 8: Documentação do fluxo de ingestão

**Files:**
- Modify: `docs/comunicacao_entre_servicos.md` (seção 5 e tabela de variáveis)
- Modify: `docs/middleware/README.md`
- Modify: `SPRINTS_BACKLOG.md`

**Interfaces:** nenhuma de código.

- [ ] **Step 1: Update the service communication doc**

Na seção 5, substituir o diagrama de sequência e o texto do `client_agent (mqtt_consumer)` pelo fluxo `Mosquitto → routing (ingest) → exchange linx.telemetry → consumidores`. Remover `INGEST_URL` e as referências a `mqtt_consumer` no `client_agent`. Adicionar `RABBIT_URL`, `RABBIT_EXCHANGE`, `MQTT_QOS` à tabela da seção 7.

- [ ] **Step 2: Update middleware README**

Descrever o `services/routing` como serviço de ingestão MQTT → RabbitMQ (validação + envelope + exchange), listando as variáveis de configuração.

- [ ] **Step 3: Update the backlog**

Em `SPRINTS_BACKLOG.md`, marcar o item do pipeline MQTT e registrar que o destino passou a ser o exchange RabbitMQ.

- [ ] **Step 4: Verify no stale references remain**

Run: `rg -n "mqtt_consumer|INGEST_URL|agent_endpoint" docs/middleware docs/comunicacao_entre_servicos.md`
Expected: sem ocorrências relevantes (ou apenas em documentos históricos de planos em `docs/superpowers/plans/`).

- [ ] **Step 5: Commit**

```bash
git add docs/comunicacao_entre_servicos.md docs/middleware/README.md SPRINTS_BACKLOG.md
git commit -m "docs(middleware): descreve ingest MQTT para exchange RabbitMQ"
```

---

### Task 9: Verificação ponta a ponta manual

**Files:** nenhum (verificação).

- [ ] **Step 1: Start the stack**

Run: `cd deploy && docker compose up -d rabbitmq mosquitto routing`
Expected: `rabbitmq` e `mosquitto` `healthy`; `routing` sem crash (`docker compose logs --tail=20 routing` mostra conexão em ambos os brokers).

- [ ] **Step 2: Publish a sample uplink**

Run:
```bash
docker compose exec mosquitto mosquitto_pub -t 'application/app1/device/devA/event/up' \
  -m '{"object":{"t":20},"rxInfo":[{"rssi":-60,"snr":7.5}],"time":"2026-10-08T12:00:00Z"}'
```
Expected: log do `routing` indicando publicação; sem `error`.

- [ ] **Step 3: Confirm the message reached the exchange**

Criar uma fila de auditoria e binding `#`, então aguardar:

Run:
```bash
docker compose exec rabbitmq rabbitmqadmin declare queue name=audit durable=true
docker compose exec rabbitmq rabbitmqadmin declare binding source=linx.telemetry destination=audit routing_key='#'
docker compose exec rabbitmq rabbitmqadmin get queue=audit count=5
```
Expected: a mensagem aparece com `routing_key=application.app1.device.devA.up` e o envelope JSON. (Se `rabbitmqadmin` não estiver disponível, validar pela management UI em `http://localhost:15672`.)

- [ ] **Step 4: Tear down**

Run: `cd deploy && docker compose down`
Expected: containers removidos (volumes preservados).

- [ ] **Step 5: Record the result**

Registrar o resultado da verificação no PR/issue correspondente. Sem commit de código.

---

## Self-Review

- **Spec coverage:** config (Task 1), validação (Task 2), envelope/routing key (Task 3), publisher com confirms/durável/persistente (Task 4), consumer QoS 1 (Task 5), wiring e remoção de HTTP/DB (Task 6), RabbitMQ no compose (Task 7), docs (Task 8), verificação ponta a ponta (Task 9). Coberto.
- **Não-objetivos** respeitados: nenhuma tarefa migra consumidores, remove `device_routes` fora do consumer, ou adiciona spool.
- **Type consistency:** `ValidUplink`/`TopicParts` (Task 2) consumidos por envelope (Task 3), consumer (Task 5), service (Task 6). `RabbitPublisher.publish(routing_key, body)` idêntico entre Task 4 e Task 6.
- **Review Focus:** cada linha tem teste na tarefa dona (1→Task 2, 2→Task 2, 3→Task 3, 4→Task 2/Task 5, 5→Task 4/Task 6).
- **Proporção:** plano descreve assinaturas e testes; corpos ficam para o implementador.
