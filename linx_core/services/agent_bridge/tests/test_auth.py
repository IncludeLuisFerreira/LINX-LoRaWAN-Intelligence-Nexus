from concurrent import futures
from uuid import uuid4

import grpc
import pytest
from linx_shared.grpc import linx_agent_pb2, linx_agent_pb2_grpc

from agent_bridge.config import settings
from agent_bridge.server import (
    AgentBridgeServicer,
    _extract_bearer_token,
    authorize,
    create_server,
    ensure_agent_service_token,
)

VALID_TOKEN = "a-valid-agent-service-token-0123456789"


class AbortError(Exception):
    """Levantado pelo contexto fake quando context.abort é chamado."""


class FakeContext:
    def __init__(self, metadata=None) -> None:
        self.aborted = None
        self._metadata = metadata or []

    def abort(self, code, details):
        self.aborted = (code, details)
        raise AbortError(details)

    def invocation_metadata(self):
        return self._metadata


class _FakeSession:
    def __init__(self, app):
        self._app = app

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def scalar(self, _stmt):
        return self._app


class FakeSessionFactory:
    """Session factory sem banco: devolve a aplicação configurada."""

    def __init__(self, app):
        self._app = app

    def __call__(self):
        return _FakeSession(self._app)


class FakeApp:
    def __init__(self):
        self.id = uuid4()


def _bearer(token):
    return [("authorization", f"Bearer {token}")]


# --- unidade: extração do metadado ---


def test_extract_bearer_token_returns_value():
    assert _extract_bearer_token(_bearer("xyz")) == "xyz"


def test_extract_bearer_token_is_case_insensitive_on_key():
    meta = [("Authorization", "Bearer xyz")]
    assert _extract_bearer_token(meta) == "xyz"


def test_extract_bearer_token_none_when_missing():
    assert _extract_bearer_token([]) is None
    assert _extract_bearer_token([("other", "value")]) is None


def test_extract_bearer_token_none_when_not_bearer():
    assert _extract_bearer_token([("authorization", "Basic xyz")]) is None


def test_extract_bearer_token_none_when_metadata_is_none():
    assert _extract_bearer_token(None) is None


# --- unidade: authorize() ---


def test_authorize_passes_with_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", VALID_TOKEN)
    context = FakeContext(metadata=_bearer(VALID_TOKEN))

    authorize(context)

    assert context.aborted is None


def test_authorize_rejects_missing_metadata(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", VALID_TOKEN)
    context = FakeContext(metadata=[])

    with pytest.raises(AbortError):
        authorize(context)

    assert context.aborted[0] == grpc.StatusCode.UNAUTHENTICATED
    assert VALID_TOKEN not in context.aborted[1]


def test_authorize_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", VALID_TOKEN)
    context = FakeContext(metadata=_bearer("outra-token-diferente"))

    with pytest.raises(AbortError):
        authorize(context)

    assert context.aborted[0] == grpc.StatusCode.UNAUTHENTICATED


def test_authorize_details_does_not_leak_secret(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", VALID_TOKEN)
    context = FakeContext(metadata=_bearer("errada"))

    with pytest.raises(AbortError):
        authorize(context)

    assert VALID_TOKEN not in context.aborted[1]


def test_authorize_fails_closed_when_token_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", "")
    context = FakeContext(metadata=_bearer(VALID_TOKEN))

    with pytest.raises(AbortError):
        authorize(context)

    assert context.aborted[0] == grpc.StatusCode.UNAUTHENTICATED


# --- unidade: ensure_agent_service_token() ---


def test_ensure_token_rejects_blank(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", "   ")
    with pytest.raises(RuntimeError):
        ensure_agent_service_token()


def test_ensure_token_rejects_placeholder(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", "changeme")
    with pytest.raises(RuntimeError):
        ensure_agent_service_token()


def test_ensure_token_rejects_short(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", "curto")
    with pytest.raises(RuntimeError):
        ensure_agent_service_token()


def test_ensure_token_accepts_strong(monkeypatch):
    monkeypatch.setattr(settings, "agent_service_token", VALID_TOKEN)
    ensure_agent_service_token()


# --- integração: servidor gRPC em memória (sem broker/DB) ---


@pytest.fixture
def grpc_server_app(monkeypatch):
    """Sobe o servicer com uma aplicação fake e devolve o channel."""
    monkeypatch.setattr(settings, "agent_service_token", VALID_TOKEN)
    monkeypatch.setattr(settings, "grpc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "grpc_port", 0)
    app = FakeApp()
    servicer = AgentBridgeServicer(session_factory=FakeSessionFactory(app))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    linx_agent_pb2_grpc.add_AgentBridgeServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield channel, app
    finally:
        channel.close()
        server.stop(0)


def test_get_app_config_over_grpc_without_token_is_unauthenticated(
    grpc_server_app,
):
    channel, app = grpc_server_app
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.GetAppConfig(linx_agent_pb2.AppId(app_id=str(app.id)))

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_get_app_config_over_grpc_wrong_token_is_unauthenticated(
    grpc_server_app,
):
    channel, app = grpc_server_app
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.GetAppConfig(
            linx_agent_pb2.AppId(app_id=str(app.id)),
            metadata=_bearer("token-incorreto-xyz"),
        )

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_get_app_config_over_grpc_with_valid_token_succeeds(grpc_server_app):
    channel, app = grpc_server_app
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)

    response = stub.GetAppConfig(
        linx_agent_pb2.AppId(app_id=str(app.id)),
        metadata=_bearer(VALID_TOKEN),
    )

    assert response.app_id == str(app.id)


def test_report_violation_over_grpc_without_token_is_unauthenticated(
    grpc_server_app,
):
    channel, _ = grpc_server_app
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)

    with pytest.raises(grpc.RpcError) as exc_info:
        stub.ReportViolation(linx_agent_pb2.Violation())

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


# --- TLS: create_server escolhe credenciais conforme config ---


def test_create_server_uses_secure_port_when_certs_present(monkeypatch):
    from unittest.mock import MagicMock

    fake_server = MagicMock()
    fake_server.add_secure_port.return_value = 1
    monkeypatch.setattr(
        "agent_bridge.server.grpc.server",
        lambda *args, **kwargs: fake_server,
    )
    monkeypatch.setattr(
        "agent_bridge.server.linx_agent_pb2_grpc"
        ".add_AgentBridgeServicer_to_server",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "agent_bridge.server.grpc.ssl_server_credentials",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(settings, "grpc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "grpc_port", 50051)
    monkeypatch.setattr(settings, "grpc_cert_chain_path", "/certs/s.crt")
    monkeypatch.setattr(settings, "grpc_private_key_path", "/certs/s.key")
    monkeypatch.setattr(settings, "grpc_ca_cert_path", "")

    create_server()

    fake_server.add_secure_port.assert_called_once()
    fake_server.add_insecure_port.assert_not_called()


def test_create_server_insecure_when_no_certs(monkeypatch):
    from unittest.mock import MagicMock

    fake_server = MagicMock()
    fake_server.add_insecure_port.return_value = 1
    monkeypatch.setattr(
        "agent_bridge.server.grpc.server",
        lambda *args, **kwargs: fake_server,
    )
    monkeypatch.setattr(
        "agent_bridge.server.linx_agent_pb2_grpc"
        ".add_AgentBridgeServicer_to_server",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(settings, "grpc_host", "127.0.0.1")
    monkeypatch.setattr(settings, "grpc_port", 50051)
    monkeypatch.setattr(settings, "grpc_cert_chain_path", "")
    monkeypatch.setattr(settings, "grpc_private_key_path", "")

    create_server()

    fake_server.add_insecure_port.assert_called_once_with("127.0.0.1:50051")
