"""Handshake mTLS real entre o servidor do SaaS e o cliente do agente."""

import logging
import shutil
import subprocess
from collections.abc import Generator
from concurrent import futures
from pathlib import Path

import grpc
import pytest
from linx_shared.grpc import linx_agent_pb2, linx_agent_pb2_grpc

from agent_bridge.config import settings
from agent_bridge.server import AgentBridgeServicer, _build_server_credentials

AGENT_TOKEN = "mtls-agent-service-token-0123456789abcdef"
AUTH_METADATA = [("authorization", f"Bearer {AGENT_TOKEN}")]
CLIENT_CN = "linx-client-agent"


def _openssl(*args: str, cwd: Path) -> None:
    subprocess.run(
        ("openssl", *args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _sign(
    endpoint: str, root: Path, ca: Path, ca_key: Path
) -> dict[str, Path]:
    ext = root / f"{endpoint}.ext"
    if endpoint == "server":
        ext.write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
            "subjectAltName=DNS:localhost,DNS:agent_bridge,IP:127.0.0.1\n"
        )
    else:
        ext.write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature\n"
            "extendedKeyUsage=clientAuth\n"
            f"subjectAltName=DNS:{CLIENT_CN}\n"
        )

    key = root / f"{endpoint}.key"
    csr = root / f"{endpoint}.csr"
    cert = root / f"{endpoint}.crt"
    cn = "localhost" if endpoint == "server" else CLIENT_CN
    _openssl(
        "req",
        "-newkey",
        "rsa:2048",
        "-sha256",
        "-nodes",
        "-keyout",
        str(key),
        "-out",
        str(csr),
        "-subj",
        f"/CN={cn}",
        cwd=root,
    )
    _openssl(
        "x509",
        "-req",
        "-in",
        str(csr),
        "-CA",
        str(ca),
        "-CAkey",
        str(ca_key),
        "-CAcreateserial",
        "-out",
        str(cert),
        "-days",
        "1",
        "-sha256",
        "-extfile",
        str(ext),
        cwd=root,
    )
    return {"key": key, "cert": cert}


@pytest.fixture(scope="module")
def certs(tmp_path_factory) -> dict[str, Path]:
    if shutil.which("openssl") is None:
        pytest.skip("openssl indisponível para o teste de mTLS")
    root = tmp_path_factory.mktemp("grpc-mtls")
    ca = root / "ca.crt"
    ca_key = root / "ca.key"
    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-sha256",
        "-nodes",
        "-keyout",
        str(ca_key),
        "-out",
        str(ca),
        "-days",
        "1",
        "-subj",
        "/CN=LINX Test CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        cwd=root,
    )
    server = _sign("server", root, ca, ca_key)
    client = _sign("client", root, ca, ca_key)

    rogue_ca = root / "rogue-ca.crt"
    rogue_key = root / "rogue-ca.key"
    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-sha256",
        "-nodes",
        "-keyout",
        str(rogue_key),
        "-out",
        str(rogue_ca),
        "-days",
        "1",
        "-subj",
        "/CN=LINX Rogue CA",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        cwd=root,
    )
    rogue = _sign("rogue-client", root, rogue_ca, rogue_key)
    return {
        "ca": ca,
        "server_key": server["key"],
        "server_cert": server["cert"],
        "client_key": client["key"],
        "client_cert": client["cert"],
        "rogue_client_key": rogue["key"],
        "rogue_client_cert": rogue["cert"],
    }


@pytest.fixture
def mtls_server(
    monkeypatch, certs
) -> Generator[tuple[grpc.Server, int], None, None]:
    monkeypatch.setattr(settings, "agent_service_token", AGENT_TOKEN)
    monkeypatch.setattr(settings, "grpc_ca_cert_path", str(certs["ca"]))
    monkeypatch.setattr(
        settings, "grpc_cert_chain_path", str(certs["server_cert"])
    )
    monkeypatch.setattr(
        settings, "grpc_private_key_path", str(certs["server_key"])
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    linx_agent_pb2_grpc.add_AgentBridgeServicer_to_server(
        AgentBridgeServicer(session_factory=lambda: None), server
    )
    credentials = _build_server_credentials()
    assert credentials is not None
    port = server.add_secure_port("127.0.0.1:0", credentials)
    server.start()
    try:
        yield server, port
    finally:
        server.stop(0)


def _channel(certs: dict[str, Path], port: int, with_cert: bool):
    if with_cert:
        credentials = grpc.ssl_channel_credentials(
            root_certificates=certs["ca"].read_bytes(),
            certificate_chain=certs["client_cert"].read_bytes(),
            private_key=certs["client_key"].read_bytes(),
        )
    else:
        credentials = grpc.ssl_channel_credentials(
            root_certificates=certs["ca"].read_bytes()
        )
    return grpc.secure_channel(f"localhost:{port}", credentials)


def test_client_with_valid_cert_is_accepted_and_logged(
    mtls_server, certs, caplog
):
    _, port = mtls_server
    channel = _channel(certs, port, with_cert=True)
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)
    try:
        with caplog.at_level(logging.INFO, logger="agent_bridge.server"):
            response = stub.ReportViolation(
                linx_agent_pb2.Violation(),
                metadata=AUTH_METADATA,
                timeout=10,
            )
    finally:
        channel.close()

    assert response.ok is False
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agent_bridge.server"
    ]
    assert any(
        "Handshake mTLS confirmado" in message and CLIENT_CN in message
        for message in messages
    )


def test_client_without_cert_is_rejected(mtls_server, certs, caplog):
    _, port = mtls_server
    channel = _channel(certs, port, with_cert=False)
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)
    try:
        with caplog.at_level(logging.INFO, logger="agent_bridge.server"):
            with pytest.raises(grpc.RpcError) as exc_info:
                stub.ReportViolation(
                    linx_agent_pb2.Violation(),
                    metadata=AUTH_METADATA,
                    timeout=10,
                )
    finally:
        channel.close()

    assert exc_info.value.code() in (
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.UNAUTHENTICATED,
    )
    assert not any(
        "Handshake mTLS confirmado" in record.getMessage()
        for record in caplog.records
    )


def test_client_with_cert_from_untrusted_ca_is_rejected(mtls_server, certs):
    _, port = mtls_server
    credentials = grpc.ssl_channel_credentials(
        root_certificates=certs["ca"].read_bytes(),
        certificate_chain=certs["rogue_client_cert"].read_bytes(),
        private_key=certs["rogue_client_key"].read_bytes(),
    )
    channel = grpc.secure_channel(f"localhost:{port}", credentials)
    stub = linx_agent_pb2_grpc.AgentBridgeStub(channel)
    try:
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.ReportViolation(
                linx_agent_pb2.Violation(),
                metadata=AUTH_METADATA,
                timeout=10,
            )
    finally:
        channel.close()

    assert exc_info.value.code() in (
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.UNAUTHENTICATED,
    )
