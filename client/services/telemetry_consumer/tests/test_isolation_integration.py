"""Teste de integração do isolamento por tenant no RabbitMQ.

Requer um broker real com credenciais administrativas via variáveis de
ambiente; caso ausentes, o teste é pulado. Não roda no CI padrão.

Env:
    RABBITMQ_ISOLATION_AMQP_HOST   host:porta AMQP (ex.: localhost:5672)
    RABBITMQ_ISOLATION_MANAGEMENT  URL da management API
    RABBITMQ_ISOLATION_ADMIN_USER
    RABBITMQ_ISOLATION_ADMIN_PASSWORD
    RABBITMQ_ISOLATION_VHOST       default "/"
"""

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
import uuid

import pytest
import rabbitpy

AMQP_HOST = os.environ.get("RABBITMQ_ISOLATION_AMQP_HOST")
MANAGEMENT = os.environ.get("RABBITMQ_ISOLATION_MANAGEMENT")
ADMIN_USER = os.environ.get("RABBITMQ_ISOLATION_ADMIN_USER")
ADMIN_PASSWORD = os.environ.get("RABBITMQ_ISOLATION_ADMIN_PASSWORD")
VHOST = os.environ.get("RABBITMQ_ISOLATION_VHOST", "/")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (AMQP_HOST and MANAGEMENT and ADMIN_USER and ADMIN_PASSWORD),
        reason="broker de isolamento não configurado (env ausente)",
    ),
]


def _derive_password(app_id: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode(), app_id.encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:40]


def _management_request(
    method: str, path: str, body: dict | None = None
) -> int:
    assert MANAGEMENT is not None
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        MANAGEMENT + path, data=data, method=method
    )
    token = base64.b64encode(
        f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()
    ).decode()
    request.add_header("Authorization", f"Basic {token}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _tenant_url(app_id: str) -> str:
    password = _derive_password(app_id, "isolation-test-secret")
    encoded_vhost = VHOST.replace("/", "%2F")
    return f"amqp://tenant.{app_id}:{password}@{AMQP_HOST}/{encoded_vhost}"


def _provision(app_id: str) -> None:
    secret = "isolation-test-secret"
    user = f"tenant.{app_id}"
    _management_request(
        "PUT",
        f"/api/users/{user}",
        {"password": _derive_password(app_id, secret), "tags": ""},
    )
    regex = rf"^linx\.telemetry\.{app_id}(\.|$)"
    encoded_vhost = VHOST.replace("/", "%2F")
    _management_request(
        "PUT",
        f"/api/permissions/{encoded_vhost}/{user}",
        {"configure": regex, "write": regex, "read": regex},
    )


@pytest.fixture
def two_apps():
    app_a = f"it-{uuid.uuid4()}"
    app_b = f"it-{uuid.uuid4()}"
    _provision(app_a)
    _provision(app_b)
    yield app_a, app_b
    for app_id in (app_a, app_b):
        _management_request("DELETE", f"/api/users/tenant.{app_id}")


def _admin_channel(connection):
    return connection.channel()


def test_tenant_cannot_declare_other_tenant_exchange(two_apps):
    app_a, app_b = two_apps
    connection = rabbitpy.Connection(_tenant_url(app_b))
    channel = connection.channel()
    exchange = rabbitpy.Exchange(
        channel, f"linx.telemetry.{app_a}", exchange_type="topic", durable=True
    )
    with pytest.raises(Exception):
        exchange.declare()
    connection.close()


def test_tenant_cannot_read_audit_queue(two_apps):
    connection = rabbitpy.Connection(_tenant_url(two_apps[0]))
    channel = connection.channel()
    queue = rabbitpy.Queue(
        channel, "linx.telemetry.audit", durable=True, auto_delete=False
    )
    with pytest.raises(Exception):
        queue.declare()
    connection.close()


def test_tenant_publishes_and_consumes_own_namespace(two_apps):
    app_a, _ = two_apps
    connection = rabbitpy.Connection(_tenant_url(app_a))
    channel = connection.channel()
    exchange = rabbitpy.Exchange(
        channel, f"linx.telemetry.{app_a}", exchange_type="topic", durable=True
    )
    exchange.declare()
    queue = rabbitpy.Queue(
        channel, f"linx.telemetry.{app_a}", durable=True, auto_delete=False
    )
    queue.declare()
    queue.bind(exchange, routing_key=f"application.{app_a}.#")
    message = rabbitpy.Message(channel, json.dumps({"app_id": app_a}).encode())
    assert message.publish(exchange, f"application.{app_a}.device.dev1.up")
    connection.close()
