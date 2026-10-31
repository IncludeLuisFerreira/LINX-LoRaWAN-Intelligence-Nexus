import httpx
import pytest
from linx_shared.core.exceptions import ExternalServiceError

from identity_api.rabbitmq_client import RabbitMQClient


def _client(handler) -> RabbitMQClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return RabbitMQClient(
        "http://rabbitmq:15672",
        "admin",
        "secret",
        vhost="/",
        client=http_client,
    )


def test_put_user_sends_password_and_empty_tags():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(204)

    client = _client(handler)
    client.put_user("tenant.app-1", "pw")

    assert captured["method"] == "PUT"
    assert captured["url"] == "http://rabbitmq:15672/api/users/tenant.app-1"
    assert '"password":"pw"' in captured["body"].replace(" ", "")
    assert '"tags":""' in captured["body"].replace(" ", "")
    assert captured["auth"] is not None


def test_set_permissions_uses_namespace_regex_and_encoded_vhost():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(204)

    client = _client(handler)
    client.set_permissions("tenant.app-1", r"^linx\.telemetry\.app-1(\.|$)")

    assert captured["url"] == (
        "http://rabbitmq:15672/api/permissions/%2F/tenant.app-1"
    )
    body = captured["body"].replace(" ", "")
    regex = r"^linx\\.telemetry\\.app-1(\\.|$)"
    assert f'"configure":"{regex}"' in body
    assert f'"write":"{regex}"' in body
    assert f'"read":"{regex}"' in body


def test_delete_user_sends_delete():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(204)

    client = _client(handler)
    client.delete_user("tenant.app-1")

    assert captured["method"] == "DELETE"
    assert captured["url"] == "http://rabbitmq:15672/api/users/tenant.app-1"


def test_delete_user_tolerates_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client(handler)
    client.delete_user("tenant.app-1")


def test_manager_error_raises_external_service_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _client(handler)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.put_user("tenant.app-1", "pw")

    assert exc_info.value.service == "rabbitmq"


def test_transport_error_raises_external_service_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = _client(handler)

    with pytest.raises(ExternalServiceError) as exc_info:
        client.put_user("tenant.app-1", "pw")

    assert exc_info.value.service == "rabbitmq"
