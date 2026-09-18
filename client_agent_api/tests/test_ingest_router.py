import asyncio

import httpx
import pytest
from starlette.testclient import TestClient

from agent.main import app

client = TestClient(app)


@pytest.fixture
def install_transport():
    clients = []

    def _install(handler):
        http_client = httpx.AsyncClient(
            base_url="http://tenant.test",
            transport=httpx.MockTransport(handler),
        )
        clients.append(http_client)
        app.state.http_client = http_client
        return http_client

    yield _install

    for http_client in clients:
        asyncio.run(http_client.aclose())
    if hasattr(app.state, "http_client"):
        del app.state.http_client


def test_ingest_forwards_and_returns_201(install_transport):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(201, json={"ok": True})

    install_transport(handler)

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True}
    assert captured["url"] == "http://tenant.test/ingest"


def test_ingest_invalid_payload_returns_422(install_transport):
    install_transport(lambda request: httpx.Response(201, json={"ok": True}))

    response = client.post("/ingest", json={"dev_eui": "dev1"})

    assert response.status_code == 422


def test_ingest_propagates_upstream_422(install_transport):
    install_transport(
        lambda request: httpx.Response(422, json={"detail": "invalid"})
    )

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 422


def test_ingest_upstream_unreachable_returns_502(install_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    install_transport(handler)

    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )

    assert response.status_code == 502
