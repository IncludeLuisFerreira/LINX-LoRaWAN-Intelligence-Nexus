#!/usr/bin/env python3
"""Teste de isolamento multi-tenant (issue #68).

Cria 2 tenants + 2 apps via identity_api, injeta telemetria marcada em cada
app via MQTT (topico application/{app_id}/device/{dev_eui}/event/up) e
verifica o isolamento por tres camadas:

  (a) leitura: GET /telemetry de cada pod do telemetry_consumer so devolve
      o marcador do proprio app (isolamento por app_id no pod/banco);
  (b) broker: credenciais RabbitMQ do app A (tenant_user/derive_tenant_
      password) NAO podem publicar no exchange linx.telemetry.{appB};
      isolamento por namespace via AMQP (regex de permissao do tenant).
      A variante MQTT (--broker mqtt) NAO isola por tenant no Mosquitto
      atual (ACL so por papel chirpstack/routing); use-a apenas quando
      houver usuario MQTT por tenant (marcado como pendencia).
  (c) rotas: GET /api/v1/tenant/{tidA}/applications/{aidB} retorna 404
      (reafirma a validacao de vinculo ja coberta pelos testes unitarios
      do identity_api).

Uso:

  # Real e2e (requer stack up):
  pip install -r scripts/requirements-e2e.txt
  python scripts/test_isolation.py --base-url http://localhost:8000 \\
      --service-token "$SERVICE_TOKEN" \\
      --consumer-a-url http://localhost:8011 --consumer-b-url http://localhost:8012 \\
      --mosquitto-host localhost --mosquitto-port 1883 \\
      --rabbitmq-host localhost --rabbitmq-port 5672 \\
      --rabbitmq-secret "$RABBITMQ_TENANT_SECRET"

  # Smoke/dry-run (sem infra):
  python scripts/test_isolation.py --dry-run

Exit code 0 = isolamento verificado; != 0 = vazamento ou falha.

Pressupostos do modo real (auditar ao rodar contra stack viva):
  - A rota de status da issue #61 (Worker 1) existe em
    GET /api/v1/applications/{app_id}/status e responde
    {"status": "RUNNING" | "PENDING" | "PROVISIONING" | "ERROR"}; o script
    faz polling com timeout. Este caminho AINDA NAO esta no develop: o e2e
    so roda apos a #61 ser mergeada. Ajuste o path se o contrato divergir.
  - Camada (b) usa AMQP por padrao: o broker RabbitMQ concede ao usuario
    tenant.{appA} apenas configure/write no regex do namespace dele,
    negando o exchange linx.telemetry.{appB} (ACCESS_REFUSED). E o
    isolamento que existe hoje. O modo MQTT so vale com usuario MQTT por
    tenant (TODO).
  - Cada pod do telemetry_consumer esta com APP_ID do respectivo app e o
    SERVICE_TOKEN compartilhado (mesmo header usado na identity_api).
  - O routing service MQTT->RabbitMQ esta ativo entre o mosquitto e a fila.
  - O segredo RabbitMQ do servidor e o mesmo usado pelo identity_api para
    derivar senhas por tenant (RABBITMQ_TENANT_SECRET).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

MARKER_A = "ISOLATION_MARKER_A"
MARKER_B = "ISOLATION_MARKER_B"
RUNNING = "RUNNING"
TERMINAL_BAD = {"ERROR", "FAILED"}

PASSWORD_LENGTH = 40
NAMESPACE_PREFIX = "linx.telemetry"


# ---------------------------------------------------------------------------
# Derivacao de credenciais RabbitMQ (espeelho de linx_shared.core.rabbitmq;
# duplicado aqui para o script nao depender do pacote instalado).
# ---------------------------------------------------------------------------


def tenant_user(app_id: str) -> str:
    return f"tenant.{app_id}"


def derive_tenant_password(app_id: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), app_id.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return encoded[:PASSWORD_LENGTH]


def tenant_namespace_regex(app_id: str) -> str:
    escaped = re.escape(app_id)
    return rf"^{re.escape(NAMESPACE_PREFIX)}\.{escaped}(\.|$)"


# ---------------------------------------------------------------------------
# Verificacao pura (sem I/O) — exercitada no dry-run e no modo real.
# ---------------------------------------------------------------------------


def check_read_isolation(
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
) -> list[str]:
    """Camada (a): pod A so ve marcador A; pod B so ve marcador B."""

    def markers(rows: list[dict[str, Any]]) -> list[str]:
        found = []
        for row in rows:
            payload = row.get("payload") or {}
            marker = payload.get("marker")
            if marker is not None:
                found.append(str(marker))
        return found

    def foreign_app_ids(rows: list[dict[str, Any]]) -> set[str]:
        own = rows[0].get("app_id") if rows else None
        return {
            str(row.get("app_id"))
            for row in rows
            if row.get("app_id") is not None and row.get("app_id") != own
        }

    failures: list[str] = []
    seen_a = set(markers(rows_a))
    seen_b = set(markers(rows_b))
    if MARKER_A not in seen_a:
        failures.append(f"pod A nao retornou dados do proprio app ({MARKER_A})")
    if MARKER_B not in seen_b:
        failures.append(f"pod B nao retornou dados do proprio app ({MARKER_B})")
    if MARKER_B in seen_a:
        failures.append(f"VAZAMENTO: marcador {MARKER_B} visivel no pod A")
    if MARKER_A in seen_b:
        failures.append(f"VAZAMENTO: marcador {MARKER_A} visivel no pod B")
    for label, rows in (("A", rows_a), ("B", rows_b)):
        foreign = foreign_app_ids(rows)
        if foreign:
            failures.append(
                f"VAZAMENTO: pod {label} devolveu "
                f"app_id(s) estrangeiro(s): {sorted(foreign)}"
            )
    return failures


def check_route_isolation(status_code: int) -> str | None:
    """Camada (c): ler app do tenant B pela rota do tenant A deve dar 404."""
    if status_code == 404:
        return None
    return (
        f"VAZAMENTO: rota de tenant A expoe app de tenant B "
        f"(status {status_code}, esperado 404)"
    )


def check_broker_namespace_denied(exc: Exception | None, connected: bool) -> str | None:
    """Camada (b): publicar no namespace de B com credenciais de A deve
    falhar com ACCESS_REFUSED (403) ou recusa analoga de permissao do
    broker. Retorna None quando o broker negou corretamente; string de
    falha quando houve vazamento ou quando o teste nao conseguiu provar."""
    if exc is not None:
        msg = str(exc).lower()
        if "access_refused" in msg or "access refused" in msg:
            return None
        if getattr(exc, "reply_code", None) == 403:
            return None
        if "not allowed" in msg or "not authorized" in msg:
            return None
        return (
            "NAO VERIFICADO: broker retornou erro que nao e recusa de "
            f"permissao (possivel falha de rede/credencial): {exc}"
        )
    if connected:
        return "VAZAMENTO: publicacao A->namespace B foi aceita pelo broker"
    return None


def uplink_payload(marker: str, app_id: str, dev_eui: str) -> dict[str, Any]:
    """Corpo MQTT no formato aceito pelo routing (validation.py).

    O routing mapeia `object` -> coluna `payload` do banco
    (middleware/services/routing/src/routing/envelope.py:15), entao o
    marcador precisa estar dentro de `object` para aparecer no GET
    /telemetry. `time` string ISO e obrigatorio. `rxInfo` e realista mas
    nao exigido.
    """
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "object": {
            "marker": marker,
            "sensor_reading": 999 if marker == MARKER_A else 111,
        },
        "deviceInfo": {"applicationId": app_id, "devEui": dev_eui},
        "rxInfo": [{"rssi": -70, "snr": 8.0}],
    }


# ---------------------------------------------------------------------------
# Portas de I/O (injetaveis; dry-run usa mocks).
# ---------------------------------------------------------------------------


class ControlPlane(Protocol):
    def create_tenant(self, name: str) -> dict[str, Any]: ...

    def create_application(self, tenant_id: str, name: str) -> dict[str, Any]: ...

    def provision(self, tenant_id: str, app_id: str) -> None: ...

    def app_status(self, tenant_id: str, app_id: str) -> str: ...

    def get_cross_status(self, tenant_id_a: str, app_id_b: str) -> int: ...


class TelemetryReader(Protocol):
    def fetch(self) -> list[dict[str, Any]]: ...


class UplinkInjector(Protocol):
    def publish(self, app_id: str, dev_eui: str, body: dict[str, Any]) -> None: ...


class BrokerProbe(Protocol):
    def try_cross_publish(
        self, app_a: str, secret: str, app_b: str
    ) -> tuple[bool, Exception | None]: ...


@dataclass
class AppContext:
    tenant_id: str
    app_id: str
    dev_eui: str
    marker: str
    reader: TelemetryReader | None = None


@dataclass
class IsolationReport:
    failures: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.failures

    def record(self, name: str, failure: str | None) -> None:
        if failure is None:
            self.checks.append(f"OK   {name}")
        else:
            self.checks.append(f"FAIL {name}")
            self.failures.append(failure)


# ---------------------------------------------------------------------------
# Adaptadores reais (lazy import: dependencias so no modo e2e).
# ---------------------------------------------------------------------------


def _httpx_client(base_url: str, service_token: str) -> Any:
    import httpx

    return httpx.Client(
        base_url=base_url,
        headers={"X-Service-Token": service_token},
        timeout=30.0,
    )


class HttpControlPlane:
    def __init__(self, base_url: str, service_token: str) -> None:
        self._client = _httpx_client(base_url, service_token)

    def _raise(self, resp: Any, what: str) -> Any:
        if resp.status_code >= 400:
            raise RuntimeError(
                f"{what} falhou: HTTP {resp.status_code} {resp.text[:200]}"
            )
        return resp

    def create_tenant(self, name: str) -> dict[str, Any]:
        resp = self._raise(
            self._client.post(
                "/api/v1/tenant/", json={"name": name, "description": "isolation test"}
            ),
            f"create_tenant({name})",
        )
        return resp.json()

    def create_application(self, tenant_id: str, name: str) -> dict[str, Any]:
        resp = self._raise(
            self._client.post(
                f"/api/v1/tenant/{tenant_id}/applications",
                json={"name": name, "description": "isolation test"},
            ),
            f"create_application({name})",
        )
        return resp.json()

    def provision(self, tenant_id: str, app_id: str) -> None:
        self._raise(
            self._client.post(
                f"/api/v1/tenant/{tenant_id}/applications/{app_id}/provision"
            ),
            f"provision({app_id})",
        )

    def app_status(self, tenant_id: str, app_id: str) -> str:
        resp = self._raise(
            self._client.get(f"/api/v1/applications/{app_id}/status"),
            f"app_status({app_id})",
        )
        return str(resp.json().get("status", "UNKNOWN"))

    def get_cross_status(self, tenant_id_a: str, app_id_b: str) -> int:
        return self._client.get(
            f"/api/v1/tenant/{tenant_id_a}/applications/{app_id_b}"
        ).status_code

    def close(self) -> None:
        self._client.close()


class HttpTelemetryReader:
    def __init__(self, url: str, service_token: str) -> None:
        self._client = _httpx_client(url, service_token)

    def fetch(self) -> list[dict[str, Any]]:
        resp = self._client.get("/telemetry", params={"limit": 200})
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GET {self._client.base_url}/telemetry -> HTTP {resp.status_code}"
            )
        return resp.json().get("items", [])


class PahoInjector:
    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        import paho.mqtt.client as mqtt

        self._mqtt = mqtt
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        if username:
            self._client.username_pw_set(username, password)
        self._client.connect(host, port)
        self._client.loop_start()

    def publish(self, app_id: str, dev_eui: str, body: dict[str, Any]) -> None:
        topic = f"application/{app_id}/device/{dev_eui}/event/up"
        info = self._client.publish(topic, json.dumps(body), qos=1)
        info.wait_for_publish(timeout=10)
        if info.rc != self._mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish em {topic} rc={info.rc}")

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()


class PahoDeniedProbe:
    """Camada (b) via MQTT: credencial de A publicando no topico de B deve
    ser recusada (ACL/autenticacao). Usar somente quando o mosquitto tiver
    usuarios por tenant; senao use RabbitmqBrokerProbe."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def try_cross_publish(
        self, app_a: str, secret: str, app_b: str
    ) -> tuple[bool, Exception | None]:
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id=f"iso-probe-{uuid.uuid4().hex[:8]}",
        )
        client.username_pw_set(
            tenant_user(app_a), derive_tenant_password(app_a, secret)
        )
        try:
            client.connect(self._host, self._port, timeout=5)
            client.loop_start()
            deadline = time.time() + 5
            while time.time() < deadline and not client.is_connected():
                time.sleep(0.1)
            if not client.is_connected():
                return False, RuntimeError("access refused (conexao recusada)")
            topic = f"application/{app_b}/device/{'DEADBEEF'}/event/up"
            info = client.publish(topic, "{}", qos=0)
            info.wait_for_publish(timeout=5)
            return info.rc == mqtt.MQTT_ERR_SUCCESS, None
        except Exception as exc:
            return False, exc
        finally:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass


class RabbitmqBrokerProbe:
    """Camada (b) via AMQP: usuario tenant.A tenta declarar/publicar no
    exchange linx.telemetry.{appB}; regex de permissão não casa -> 403."""

    def __init__(self, host: str, port: int, vhost: str = "/") -> None:
        self._host = host
        self._port = port
        self._vhost = vhost

    def try_cross_publish(
        self, app_a: str, secret: str, app_b: str
    ) -> tuple[bool, Exception | None]:
        import pika

        creds = pika.PlainCredentials(
            tenant_user(app_a), derive_tenant_password(app_a, secret)
        )
        params = pika.ConnectionParameters(
            host=self._host,
            port=self._port,
            virtual_host=self._vhost,
            credentials=creds,
            socket_timeout=10,
            heartbeat=None,
        )
        try:
            conn = pika.BlockingConnection(params)
            try:
                channel = conn.channel()
                channel.confirm_delivery()
                channel.basic_publish(
                    exchange=f"{NAMESPACE_PREFIX}.{app_b}",
                    routing_key=f"application.{app_b}.device.probe.up",
                    body=b"{}",
                )
                return True, None
            finally:
                if conn.is_open:
                    conn.close()
        except Exception as exc:
            return False, exc


# ---------------------------------------------------------------------------
# Orquestração e2e.
# ---------------------------------------------------------------------------


def wait_running(
    control: ControlPlane,
    tenant_id: str,
    app_id: str,
    timeout: float,
    interval: float,
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = control.app_status(tenant_id, app_id)
        if status == RUNNING:
            return
        if status in TERMINAL_BAD:
            raise RuntimeError(f"app {app_id} terminou em {status}")
        time.sleep(interval)
    raise RuntimeError(f"timeout aguardando RUNNING de {app_id}")


def run_e2e(args: argparse.Namespace, log: Callable[[str], None]) -> IsolationReport:
    for name, module in (
        ("httpx", "httpx"),
        ("paho.mqtt.client", "paho"),
        ("pika", "pika"),
    ):
        try:
            __import__(module)
        except ImportError:
            raise SystemExit(
                f"dependencia {name} ausente; instale com "
                "pip install -r scripts/requirements-e2e.txt ou use --dry-run"
            )

    control = HttpControlPlane(args.base_url, args.service_token)
    report = IsolationReport()
    suffix = uuid.uuid4().hex[:8]
    contexts: list[AppContext] = []
    for marker, label in ((MARKER_A, "A"), (MARKER_B, "B")):
        tenant = control.create_tenant(f"iso-{label}-{suffix}")
        app = control.create_application(tenant["id"], f"iso-app-{label}-{suffix}")
        control.provision(tenant["id"], app["id"])
        wait_running(control, tenant["id"], app["id"], args.provision_timeout, 2.0)
        contexts.append(
            AppContext(
                tenant_id=tenant["id"],
                app_id=app["id"],
                dev_eui=uuid.uuid4().hex[:16],
                marker=marker,
            )
        )

    injector = PahoInjector(
        args.mosquitto_host,
        args.mosquitto_port,
        args.mosquitto_username,
        args.mosquitto_password,
    )
    for ctx in contexts:
        log(f"publicando uplink {ctx.marker} em application/{ctx.app_id}/...")
        injector.publish(
            ctx.app_id, ctx.dev_eui, uplink_payload(ctx.marker, ctx.app_id, ctx.dev_eui)
        )
    injector.close()

    log(f"aguardando {args.ingest_settle_seconds}s para ingestao")
    time.sleep(args.ingest_settle_seconds)

    readers = {
        "A": HttpTelemetryReader(
            args.consumer_a_url, args.service_token_a or args.service_token
        ),
        "B": HttpTelemetryReader(
            args.consumer_b_url, args.service_token_b or args.service_token
        ),
    }
    rows_a = readers["A"].fetch()
    rows_b = readers["B"].fetch()
    report.record(
        "(a) leitura /telemetry por pod", _first(check_read_isolation(rows_a, rows_b))
    )

    if args.broker == "mqtt":
        log(
            "AVISO: modo MQTT nao isola por tenant no Mosquitto atual "
            "(ACL so por papel, sem usuario MQTT por tenant). Camada (b) "
            "marcada como NAO VERIFICADO; prefira --broker amqp (TODO #68)."
        )
        report.record(
            "(b) broker/mqtt negando A->B",
            "NAO VERIFICADO: isolamento MQTT por tenant ainda nao existe "
            "no broker (use --broker amqp)",
        )
    else:
        probe = RabbitmqBrokerProbe(
            args.rabbitmq_host, args.rabbitmq_port, args.rabbitmq_vhost
        )
        connected, exc = probe.try_cross_publish(
            contexts[0].app_id, args.rabbitmq_secret, contexts[1].app_id
        )
        report.record(
            "(b) broker/amqp negando A->B",
            check_broker_namespace_denied(exc, connected),
        )

    cross = control.get_cross_status(contexts[0].tenant_id, contexts[1].app_id)
    report.record("(c) rota tenant A sobre app B", check_route_isolation(cross))

    control.close()
    return report


def _first(items: list[str]) -> str | None:
    return items[0] if items else None


# ---------------------------------------------------------------------------
# Dry-run: valida estrutura com mocks, sem infra.
# ---------------------------------------------------------------------------


class FakeControl:
    def __init__(self) -> None:
        self.tenants: dict[str, dict[str, Any]] = {}
        self.apps: dict[str, dict[str, Any]] = {}
        self.provisioned: set[str] = set()
        self._seq = 0

    def _id(self) -> str:
        self._seq += 1
        return str(uuid.UUID(int=self._seq))

    def create_tenant(self, name: str) -> dict[str, Any]:
        tid = self._id()
        self.tenants[tid] = {"id": tid, "name": name}
        return self.tenants[tid]

    def create_application(self, tenant_id: str, name: str) -> dict[str, Any]:
        aid = self._id()
        self.apps[aid] = {"id": aid, "name": name, "tenant_id": tenant_id}
        return self.apps[aid]

    def provision(self, tenant_id: str, app_id: str) -> None:
        self.provisioned.add(app_id)

    def app_status(self, tenant_id: str, app_id: str) -> str:
        return RUNNING if app_id in self.provisioned else "PENDING"

    def get_cross_status(self, tenant_id_a: str, app_id_b: str) -> int:
        app = self.apps[app_id_b]
        return 200 if app["tenant_id"] == tenant_id_a else 404


class FakeReader:
    def __init__(
        self, own_marker: str, own_app_id: str, poisoned: bool = False
    ) -> None:
        rows = [{"app_id": own_app_id, "payload": {"marker": own_marker}}]
        if poisoned:
            other = MARKER_B if own_marker == MARKER_A else MARKER_A
            rows.append({"app_id": "other", "payload": {"marker": other}})
        self._rows = rows

    def fetch(self) -> list[dict[str, Any]]:
        return self._rows


class FakeBroker:
    def __init__(self, allow_cross: bool = False) -> None:
        self._allow = allow_cross

    def try_cross_publish(
        self, app_a: str, secret: str, app_b: str
    ) -> tuple[bool, Exception | None]:
        if self._allow:
            return True, None
        return False, RuntimeError("ACCESS_REFUSED - login refused")


class FakeInjector:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict[str, Any]]] = []

    def publish(self, app_id: str, dev_eui: str, body: dict[str, Any]) -> None:
        self.published.append((app_id, dev_eui, body))


def run_dry() -> IsolationReport:
    report = IsolationReport()
    control = FakeControl()
    tenant_a = control.create_tenant("iso-A")
    tenant_b = control.create_tenant("iso-B")
    app_a = control.create_application(tenant_a["id"], "app-A")
    app_b = control.create_application(tenant_b["id"], "app-B")
    control.provision(tenant_a["id"], app_a["id"])
    control.provision(tenant_b["id"], app_b["id"])
    report.record(
        "dry: provisionamento atinge RUNNING",
        (
            None
            if control.app_status(tenant_a["id"], app_a["id"]) == RUNNING
            else "app A nao chegou a RUNNING"
        ),
    )

    injector = FakeInjector()
    injector.publish(app_a["id"], "DEVA", uplink_payload(MARKER_A, app_a["id"], "DEVA"))
    injector.publish(app_b["id"], "DEVB", uplink_payload(MARKER_B, app_b["id"], "DEVB"))
    ok_shape = all(
        {"time", "object", "deviceInfo"} <= set(body)
        and body["object"].get("marker") in (MARKER_A, MARKER_B)
        for _, _, body in injector.published
    )
    report.record(
        "dry: shape do uplink casa com routing/validation.py",
        None if ok_shape else "payload fora do schema esperado",
    )

    rows_a = FakeReader(MARKER_A, app_a["id"]).fetch()
    rows_b = FakeReader(MARKER_B, app_b["id"]).fetch()
    report.record(
        "dry: (a) leitura isolada", _first(check_read_isolation(rows_a, rows_b))
    )
    poisoned_a = FakeReader(MARKER_A, app_a["id"], poisoned=True).fetch()
    detected = bool(check_read_isolation(poisoned_a, rows_b))
    report.record(
        "dry: (a) deteccao de vazamento",
        None if detected else "vazamento nao detectado",
    )

    connected, exc = FakeBroker().try_cross_publish(app_a["id"], "s", app_b["id"])
    report.record(
        "dry: (b) broker nega A->B", check_broker_namespace_denied(exc, connected)
    )
    leak_connected, leak_exc = FakeBroker(allow_cross=True).try_cross_publish(
        app_a["id"], "s", app_b["id"]
    )
    leak_detected = check_broker_namespace_denied(leak_exc, leak_connected) is not None
    report.record(
        "dry: (b) deteccao de vazamento",
        None if leak_detected else "broker cruzado nao detectado",
    )

    regex = tenant_namespace_regex(app_a["id"])
    crosses_own = re.match(regex, f"{NAMESPACE_PREFIX}.{app_a['id']}") is not None
    crosses_other = re.match(regex, f"{NAMESPACE_PREFIX}.{app_b['id']}") is not None
    report.record(
        "dry: regex RabbitMQ ancora namespace proprio",
        None if crosses_own and not crosses_other else "regex de namespace nao isola",
    )

    report.record(
        "dry: (c) rota 404 para app alheio",
        check_route_isolation(control.get_cross_status(tenant_a["id"], app_b["id"])),
    )
    return report


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="valida estrutura sem infra"
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8000", help="URL do identity_api"
    )
    parser.add_argument(
        "--service-token", default="", help="X-Service-Token da identity_api"
    )
    parser.add_argument(
        "--service-token-a",
        default="",
        help="token do pod A (default: --service-token)",
    )
    parser.add_argument(
        "--service-token-b",
        default="",
        help="token do pod B (default: --service-token)",
    )
    parser.add_argument("--mosquitto-host", default="localhost")
    parser.add_argument("--mosquitto-port", type=int, default=1883)
    parser.add_argument("--mosquitto-username", default="chirpstack")
    parser.add_argument("--mosquitto-password", default="")
    parser.add_argument("--consumer-a-url", default="http://localhost:8011")
    parser.add_argument("--consumer-b-url", default="http://localhost:8012")
    parser.add_argument(
        "--broker", choices=("amqp", "mqtt"), default="amqp", help="camada (b)"
    )
    parser.add_argument("--rabbitmq-host", default="localhost")
    parser.add_argument("--rabbitmq-port", type=int, default=5672)
    parser.add_argument("--rabbitmq-vhost", default="/")
    parser.add_argument(
        "--rabbitmq-secret",
        default="",
        help="segredo do servidor p/ derivar senha de tenant",
    )
    parser.add_argument("--provision-timeout", type=float, default=300.0)
    parser.add_argument("--ingest-settle-seconds", type=float, default=10.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    def log(msg: str) -> None:
        print(msg, flush=True)

    if args.dry_run:
        log("== modo dry-run (sem infra) ==")
        report = run_dry()
    else:
        missing = [
            n
            for n, v in (
                ("--service-token", args.service_token),
                ("--rabbitmq-secret", args.rabbitmq_secret),
            )
            if not v
        ]
        if missing:
            log(f"faltam credenciais: {', '.join(missing)} (ou rode --dry-run)")
            return 2
        log("== modo e2e ==")
        try:
            report = run_e2e(args, log)
        except Exception as exc:
            log(f"FALHA de infraestrutura/execucao: {exc}")
            return 3

    for line in report.checks:
        log(line)
    if report.ok():
        log("RESULTADO: isolamento OK (todos os checks passaram)")
        return 0
    log("RESULTADO: FALHAS de isolamento:")
    for failure in report.failures:
        log(f"  - {failure}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
