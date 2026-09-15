from collections.abc import Generator
from concurrent import futures
from uuid import uuid4

import grpc
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from linx.core.config import settings
from linx.db.base import engine
from linx.grpc import saas_agent_pb2, saas_agent_pb2_grpc
from linx.grpc_server import AgentBridgeServicer
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


def test_ack_handlers_return_ok():
    servicer = AgentBridgeServicer()

    assert (
        servicer.IngestTelemetry(
            saas_agent_pb2.TelemetryEvent(), FakeContext()
        ).ok
        is True
    )
    assert servicer.SyncRule(saas_agent_pb2.Rule(), FakeContext()).ok is True
    assert (
        servicer.ReportViolation(saas_agent_pb2.Violation(), FakeContext()).ok
        is True
    )


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
