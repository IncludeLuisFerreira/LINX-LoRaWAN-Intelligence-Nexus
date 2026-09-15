import socket
from collections.abc import Generator
from concurrent import futures
from unittest.mock import MagicMock
from uuid import uuid4

import grpc
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from linx import grpc_server as grpc_server_module
from linx.core.config import settings
from linx.db.base import engine
from linx.grpc import saas_agent_pb2, saas_agent_pb2_grpc
from linx.grpc_server import (
    AgentBridgeServicer,
    create_server,
    is_grpc_serving,
)
from linx.main import app
from linx.models.application import Application
from linx.models.tenant import Tenant


class AbortError(Exception):
    """Levantado pelo contexto fake quando context.abort é chamado."""


class FakeContext:
    """Contexto gRPC mínimo, que registra e reproduz o abort."""

    def __init__(self) -> None:
        self.aborted: tuple[grpc.StatusCode, str] | None = None

    def abort(self, code: grpc.StatusCode, details: str) -> None:
        self.aborted = (code, details)
        raise AbortError(details)


class BrokenSessionFactory:
    """Session factory que simula indisponibilidade do banco."""

    def __call__(self):
        raise SQLAlchemyError("banco indisponível")


@pytest.fixture
def session_factory() -> Generator[sessionmaker, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint"
    )
    try:
        yield factory
    finally:
        transaction.rollback()
        connection.close()


def _create_application(factory: sessionmaker) -> str:
    with factory() as session:
        tenant = Tenant(name="Tenant gRPC")
        session.add(tenant)
        session.flush()
        application = Application(tenant_id=tenant.id, name="App gRPC")
        session.add(application)
        session.commit()
        return str(application.id)


def test_get_app_config_returns_config_for_existing_application(
    session_factory,
):
    app_id = _create_application(session_factory)
    servicer = AgentBridgeServicer(session_factory=session_factory)
    db_url = make_url(settings.database_url)

    response = servicer.GetAppConfig(
        saas_agent_pb2.AppId(app_id=app_id), FakeContext()
    )

    assert response.app_id == app_id
    assert response.db_host == (db_url.host or "")
    assert response.db_port == (db_url.port or 0)
    assert response.db_name == (db_url.database or "")
    assert response.db_user == (db_url.username or "")
    assert response.db_password == (db_url.password or "")
    assert response.mqtt_topic == f"application/{app_id}/device/+/event/up"


def test_get_app_config_aborts_not_found_for_unknown_application(
    session_factory,
):
    servicer = AgentBridgeServicer(session_factory=session_factory)
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.GetAppConfig(
            saas_agent_pb2.AppId(app_id=str(uuid4())), context
        )

    assert context.aborted is not None
    assert context.aborted[0] == grpc.StatusCode.NOT_FOUND


def test_get_app_config_aborts_invalid_argument_for_invalid_app_id():
    servicer = AgentBridgeServicer()
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.GetAppConfig(
            saas_agent_pb2.AppId(app_id="nao-e-uuid"), context
        )

    assert context.aborted is not None
    assert context.aborted[0] == grpc.StatusCode.INVALID_ARGUMENT


def test_get_app_config_aborts_unavailable_when_database_fails():
    servicer = AgentBridgeServicer(session_factory=BrokenSessionFactory())
    context = FakeContext()

    with pytest.raises(AbortError):
        servicer.GetAppConfig(
            saas_agent_pb2.AppId(app_id=str(uuid4())), context
        )

    assert context.aborted is not None
    assert context.aborted[0] == grpc.StatusCode.UNAVAILABLE


def test_report_violation_returns_not_implemented_ack():
    servicer = AgentBridgeServicer()

    response = servicer.ReportViolation(
        saas_agent_pb2.Violation(), FakeContext()
    )

    assert response.ok is False
    assert response.error == "not implemented"


def test_create_server_binds_configured_address(monkeypatch):
    monkeypatch.setattr(settings, "grpc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "grpc_port", 0)

    server = create_server()
    try:
        assert isinstance(server, grpc.Server)
        server.start()
    finally:
        server.stop(0)


def test_create_server_raises_when_bind_fails(monkeypatch):
    fake_server = MagicMock()
    fake_server.add_insecure_port.return_value = 0
    monkeypatch.setattr(
        "linx.grpc_server.grpc.server", lambda *args, **kwargs: fake_server
    )
    monkeypatch.setattr(
        "linx.grpc_server.saas_agent_pb2_grpc"
        ".add_AgentBridgeServicer_to_server",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(RuntimeError):
        create_server()


def test_serve_starts_and_waits_for_termination(monkeypatch):
    fake_server = MagicMock()
    monkeypatch.setattr("linx.grpc_server.create_server", lambda: fake_server)

    grpc_server_module.serve()

    fake_server.start.assert_called_once()
    fake_server.wait_for_termination.assert_called_once()


def test_lifespan_starts_and_stops_grpc_server(monkeypatch):
    fake_server = MagicMock()
    monkeypatch.setattr("linx.main.create_server", lambda: fake_server)
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: True)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        fake_server.start.assert_called_once()

    fake_server.stop.assert_called_once_with(grace=5)
    fake_server.stop.return_value.wait.assert_called_once()


@pytest.fixture
def grpc_channel(session_factory) -> Generator[grpc.Channel, None, None]:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    saas_agent_pb2_grpc.add_AgentBridgeServicer_to_server(
        AgentBridgeServicer(session_factory=session_factory), server
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield channel
    finally:
        channel.close()
        server.stop(0)


def test_get_app_config_over_grpc(grpc_channel, session_factory):
    app_id = _create_application(session_factory)
    stub = saas_agent_pb2_grpc.AgentBridgeStub(grpc_channel)

    response = stub.GetAppConfig(saas_agent_pb2.AppId(app_id=app_id))

    assert response.app_id == app_id
    assert response.mqtt_topic == f"application/{app_id}/device/+/event/up"


def test_get_app_config_over_grpc_not_found(grpc_channel):
    stub = saas_agent_pb2_grpc.AgentBridgeStub(grpc_channel)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.GetAppConfig(saas_agent_pb2.AppId(app_id=str(uuid4())))

    assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND


def test_report_violation_over_grpc(grpc_channel):
    stub = saas_agent_pb2_grpc.AgentBridgeStub(grpc_channel)

    response = stub.ReportViolation(saas_agent_pb2.Violation())

    assert response.ok is False
    assert response.error == "not implemented"


def test_client_hosted_rpcs_are_unimplemented_on_saas(grpc_channel):
    stub = saas_agent_pb2_grpc.AgentBridgeStub(grpc_channel)

    for rpc, request in (
        (stub.IngestTelemetry, saas_agent_pb2.TelemetryEvent()),
        (stub.SyncRule, saas_agent_pb2.Rule()),
    ):
        with pytest.raises(grpc.RpcError) as exc_info:
            rpc(request)
        assert exc_info.value.code() == grpc.StatusCode.UNIMPLEMENTED


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_is_grpc_serving_true_when_port_is_open():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    try:
        assert is_grpc_serving(host="127.0.0.1", port=port) is True
    finally:
        listener.close()


def test_is_grpc_serving_false_when_port_is_closed():
    port = _free_port()

    assert is_grpc_serving(host="127.0.0.1", port=port) is False


def test_is_grpc_serving_false_when_port_is_zero():
    assert is_grpc_serving(host="127.0.0.1", port=0) is False


def test_is_grpc_serving_normalizes_wildcard_host(monkeypatch):
    listener = socket.socket()
    listener.bind(("0.0.0.0", 0))
    listener.listen()
    port = listener.getsockname()[1]
    monkeypatch.setattr(settings, "grpc_host", "0.0.0.0")
    monkeypatch.setattr(settings, "grpc_port", port)
    try:
        assert is_grpc_serving() is True
    finally:
        listener.close()


def test_is_grpc_serving_true_for_real_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        assert is_grpc_serving(host="127.0.0.1", port=port) is True
    finally:
        server.stop(0)


def test_is_grpc_serving_false_for_out_of_range_port():
    assert is_grpc_serving(host="127.0.0.1", port=70000) is False


def _capture_connect(monkeypatch) -> list:
    captured: list = []

    def fake_create_connection(address, timeout):
        captured.append((address, timeout))
        return MagicMock()

    monkeypatch.setattr(
        "linx.grpc_server.socket.create_connection", fake_create_connection
    )
    return captured


def test_is_grpc_serving_normalizes_empty_host(monkeypatch):
    captured = _capture_connect(monkeypatch)

    assert is_grpc_serving(host="", port=50051) is True
    assert captured == [(("127.0.0.1", 50051), 1.0)]


def test_is_grpc_serving_accepts_hostname(monkeypatch):
    captured = _capture_connect(monkeypatch)

    assert is_grpc_serving(host="localhost", port=50051) is True
    assert captured[0][0] == ("localhost", 50051)


def test_is_grpc_serving_normalizes_ipv6_unspecified(monkeypatch):
    captured = _capture_connect(monkeypatch)

    assert is_grpc_serving(host="::", port=50051) is True
    assert captured[0][0] == ("::1", 50051)


def test_is_grpc_serving_normalizes_expanded_ipv6_unspecified(monkeypatch):
    captured = _capture_connect(monkeypatch)

    assert is_grpc_serving(host="0:0:0:0:0:0:0:0", port=50051) is True
    assert captured[0][0] == ("::1", 50051)


def test_create_server_brackets_ipv6_bind_address(monkeypatch):
    fake_server = MagicMock()
    fake_server.add_insecure_port.return_value = 1
    monkeypatch.setattr(
        "linx.grpc_server.grpc.server", lambda *args, **kwargs: fake_server
    )
    monkeypatch.setattr(
        "linx.grpc_server.saas_agent_pb2_grpc"
        ".add_AgentBridgeServicer_to_server",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(settings, "grpc_host", "::")
    monkeypatch.setattr(settings, "grpc_port", 50051)

    create_server()

    fake_server.add_insecure_port.assert_called_once_with("[::]:50051")
