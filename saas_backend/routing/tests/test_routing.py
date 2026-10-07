from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import paho.mqtt.client as mqtt
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from routing.routing import (
    DEFAULT_TOPIC,
    UplinkRouter,
    build_ingest_payload,
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
    payload = {
        "object": {"t": 20},
        "rxInfo": [{"rssi": -60, "snr": 7.5}],
        "deviceInfo": {"devEui": "dev1"},
    }

    assert (
        route_uplink(
            "dev1", payload, session_factory=factory, http_client=http
        )
        is True
    )

    http.post.assert_called_once_with(
        "http://agent:8001/ingest",
        json={
            "dev_eui": "dev1",
            "payload": {"t": 20},
            "rssi": -60,
            "snr": 7.5,
        },
    )


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

    http.post.assert_called_once_with(
        "http://agent:8001/ingest", json={"dev_eui": "dev1", "payload": {}}
    )


def test_build_ingest_payload_extracts_object_and_radio():
    event = {
        "object": {"t": 20},
        "rxInfo": [{"rssi": -60, "snr": 7.5}],
        "deviceInfo": {"devEui": "dev1"},
    }

    assert build_ingest_payload("dev1", event) == {
        "dev_eui": "dev1",
        "payload": {"t": 20},
        "rssi": -60,
        "snr": 7.5,
    }


def test_build_ingest_payload_missing_object_is_empty():
    result = build_ingest_payload("dev1", {})

    assert result["payload"] == {}
    assert "rssi" not in result
    assert "snr" not in result


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


def test_route_uplink_rejects_non_http_scheme(caplog):
    route = SimpleNamespace(agent_endpoint="ftp://agent:21")
    factory = _session_factory_returning(route)
    http = _ok_http()

    with caplog.at_level("WARNING"):
        assert (
            route_uplink("dev1", {}, session_factory=factory, http_client=http)
            is False
        )

    http.post.assert_not_called()
    assert "esquema inválido" in caplog.text


class _CapturingSession:
    def __init__(self, route, statements):
        self._route = route
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def scalar(self, statement):
        self._statements.append(statement)
        return self._route


def _capturing_session_factory(route, statements):
    factory = MagicMock()
    factory.return_value = _CapturingSession(route, statements)
    return factory


def _compiled_sql(statement):
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_route_uplink_lookup_is_case_insensitive():
    route = SimpleNamespace(agent_endpoint="http://agent:8001")
    statements = []
    factory = _capturing_session_factory(route, statements)
    http = _ok_http()

    assert (
        route_uplink("AA11BB22", {}, session_factory=factory, http_client=http)
        is True
    )

    assert len(statements) == 1
    sql = _compiled_sql(statements[0])
    assert "lower(device_routes.dev_eui)" in sql
    assert "aa11bb22" in sql


def test_route_uplink_two_dev_euis_go_to_distinct_endpoints():
    statements = []
    http = _ok_http()

    route1 = SimpleNamespace(agent_endpoint="http://agent1:8001")
    route2 = SimpleNamespace(agent_endpoint="http://agent2:8002")

    assert route_uplink(
        "dev1",
        {},
        session_factory=_capturing_session_factory(route1, statements),
        http_client=http,
    )
    assert route_uplink(
        "dev2",
        {},
        session_factory=_capturing_session_factory(route2, statements),
        http_client=http,
    )

    assert len(statements) == 2
    assert "dev1" in _compiled_sql(statements[0])
    assert "dev2" in _compiled_sql(statements[1])

    posted_urls = [call.args[0] for call in http.post.call_args_list]
    assert posted_urls == [
        "http://agent1:8001/ingest",
        "http://agent2:8002/ingest",
    ]


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
    router.http_client.close()
    router.http_client = MagicMock()
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


def test_on_message_enqueues_without_routing(monkeypatch):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock(return_value=True)
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)
    message = MagicMock()
    message.topic = "application/1/device/dev1/event/up"
    message.payload = b'{"dev_eui": "dev1", "payload": {"t": 20}}'

    router.on_message(router.client, None, message)

    assert router._q.qsize() == 1
    fake_route_uplink.assert_not_called()


def test_handle_uplink_routes(monkeypatch):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock(return_value=True)
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)

    router._handle_uplink(
        "application/1/device/dev1/event/up",
        b'{"dev_eui": "dev1", "payload": {"t": 20}}',
    )

    fake_route_uplink.assert_called_once()
    args, kwargs = fake_route_uplink.call_args
    assert args[0] == "dev1"
    assert args[1] == {"dev_eui": "dev1", "payload": {"t": 20}}
    assert kwargs["http_client"] is router.http_client


def test_handle_uplink_invalid_json_does_not_route(monkeypatch):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock()
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)

    router._handle_uplink("application/1/device/dev1/event/up", b"not-json")

    fake_route_uplink.assert_not_called()


def test_handle_uplink_invalid_topic_does_not_route(monkeypatch):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock()
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)

    router._handle_uplink("weird/topic", b'{"a": 1}')

    fake_route_uplink.assert_not_called()


def test_handle_uplink_non_dict_json_does_not_route(monkeypatch, caplog):
    router = _router_with_mock_client()
    fake_route_uplink = MagicMock()
    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)

    with caplog.at_level("WARNING"):
        router._handle_uplink("application/1/device/dev1/event/up", b"[1, 2]")

    fake_route_uplink.assert_not_called()
    assert "não é um objeto JSON" in caplog.text


def test_worker_processes_queue_item(monkeypatch):
    router = _router_with_mock_client()
    seen = {}

    def fake_route_uplink(dev_eui, payload, **kwargs):
        seen["dev_eui"] = dev_eui
        seen["payload"] = payload
        router._stop_event.set()

    monkeypatch.setattr("routing.routing.route_uplink", fake_route_uplink)

    router._q.put(
        (
            "application/1/device/dev1/event/up",
            b'{"dev_eui": "dev1", "payload": {"t": 20}}',
        )
    )

    router._worker()

    assert seen["dev_eui"] == "dev1"
    assert seen["payload"] == {"dev_eui": "dev1", "payload": {"t": 20}}
    assert router._q.qsize() == 0


def test_stop_disconnects_and_joins():
    router = _router_with_mock_client()

    router.stop()

    assert router._stop_event.is_set()
    router.client.disconnect.assert_called_once()
    router.http_client.close.assert_called_once()
