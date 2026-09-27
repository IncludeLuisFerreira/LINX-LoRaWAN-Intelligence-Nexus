from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import paho.mqtt.client as mqtt
from sqlalchemy.exc import SQLAlchemyError

from routing.routing import (
    DEFAULT_TOPIC,
    UplinkRouter,
    extract_dev_eui,
    route_uplink,
)


def _session_factory_returning(route):
    session = MagicMock()
    session.scalar.return_value = route
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    return factory


def _failing_session_factory():
    def factory():
        raise SQLAlchemyError("banco indisponível")

    return factory


def _ok_http():
    http = MagicMock()
    http.post.return_value = MagicMock(status_code=201)
    return http


def test_extract_dev_eui_valid_topic():
    assert (
        extract_dev_eui("application/abc/device/0011223344556677/event/up")
        == "0011223344556677"
    )


def test_extract_dev_eui_invalid_topic_returns_none():
    assert extract_dev_eui("other/abc/device/x/event/up") is None
    assert extract_dev_eui("application/abc/other/x/event/up") is None
    assert extract_dev_eui("application/abc/device") is None
    assert extract_dev_eui("short") is None


def test_route_uplink_posts_to_agent_endpoint():
    route = SimpleNamespace(agent_endpoint="http://agent:8001")
    factory = _session_factory_returning(route)
    http = _ok_http()
    payload = {"dev_eui": "dev1", "payload": {"t": 20}}

    assert (
        route_uplink(
            "dev1", payload, session_factory=factory, http_client=http
        )
        is True
    )

    http.post.assert_called_once_with("http://agent:8001/ingest", json=payload)


def test_route_uplink_without_route_logs_and_returns_false(caplog):
    factory = _session_factory_returning(None)
    http = _ok_http()

    with caplog.at_level("WARNING"):
        assert (
            route_uplink("dev1", {}, session_factory=factory, http_client=http)
            is False
        )

    http.post.assert_not_called()
    assert "Sem rota" in caplog.text


def test_route_uplink_with_null_endpoint_returns_false(caplog):
    route = SimpleNamespace(agent_endpoint=None)
    factory = _session_factory_returning(route)
    http = _ok_http()

    with caplog.at_level("WARNING"):
        assert (
            route_uplink("dev1", {}, session_factory=factory, http_client=http)
            is False
        )

    http.post.assert_not_called()


def test_route_uplink_strips_trailing_slash():
    route = SimpleNamespace(agent_endpoint="http://agent:8001/")
    factory = _session_factory_returning(route)
    http = _ok_http()

    route_uplink("dev1", {}, session_factory=factory, http_client=http)

    http.post.assert_called_once_with("http://agent:8001/ingest", json={})


def test_route_uplink_post_failure_logs_and_returns_false(caplog):
    route = SimpleNamespace(agent_endpoint="http://agent:8001")
    factory = _session_factory_returning(route)
    http = MagicMock()
    http.post.side_effect = httpx.ConnectError("boom")

    with caplog.at_level("ERROR"):
        assert (
            route_uplink("dev1", {}, session_factory=factory, http_client=http)
            is False
        )

    assert "Falha ao encaminhar" in caplog.text


def test_route_uplink_db_error_returns_false(caplog):
    http = _ok_http()

    with caplog.at_level("ERROR"):
        assert (
            route_uplink(
                "dev1",
                {},
                session_factory=_failing_session_factory(),
                http_client=http,
            )
            is False
        )

    http.post.assert_not_called()


def _router_with_mock_client():
    router = UplinkRouter()
    router.client = MagicMock()
    return router


def test_router_default_topic():
    router = _router_with_mock_client()

    assert router.topic == DEFAULT_TOPIC


def test_on_connect_success_subscribes_to_topic():
    router = _router_with_mock_client()
    reason_code = mqtt.convert_connack_rc_to_reason_code(0)

    router.on_connect(router.client, None, None, reason_code, None)

    router.client.subscribe.assert_called_once_with(router.topic)


def test_on_connect_failure_does_not_subscribe():
    router = _router_with_mock_client()
    reason_code = mqtt.convert_connack_rc_to_reason_code(1)

    router.on_connect(router.client, None, None, reason_code, None)

    router.client.subscribe.assert_not_called()


def test_on_message_routes_uplink(monkeypatch):
    router = _router_with_mock_client()
    router.http_client = MagicMock()
    fake_route_uplink = MagicMock(return_value=True)
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b'{"dev_eui": "dev1", "payload": {"t": 20}}'

    router.on_message(router.client, None, message)

    fake_route_uplink.assert_called_once()
    args, kwargs = fake_route_uplink.call_args
    assert args[0] == "dev1"
    assert args[1] == {"dev_eui": "dev1", "payload": {"t": 20}}
    assert kwargs["http_client"] is router.http_client


def test_on_message_invalid_json_does_not_route(monkeypatch):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock()
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b"not-json"

    router.on_message(router.client, None, message)

    fake_route_uplink.assert_not_called()


def test_on_message_invalid_topic_does_not_route(monkeypatch):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock()
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)
    message = MagicMock()
    message.topic = "weird/topic"
    message.payload = b'{"a": 1}'

    router.on_message(router.client, None, message)

    fake_route_uplink.assert_not_called()
