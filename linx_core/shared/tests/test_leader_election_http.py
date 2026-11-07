import http.client
import json
import urllib.error
from uuid import UUID

import pytest

from linx_shared.coordination import leader
from linx_shared.coordination.leader import (
    InClusterLeaseClient,
    LeaderElectionError,
    LeaseConflictError,
    resolve_identity,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _install(monkeypatch, response=None, error=None):
    calls: list = []

    def fake_urlopen(request, context=None, timeout=None):
        calls.append(request)
        if error is not None:
            raise error
        return response if response is not None else FakeResponse({})

    monkeypatch.setattr(leader.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        leader.ssl, "create_default_context", lambda cafile=None: object()
    )
    client = InClusterLeaseClient(
        base_url="https://k8s", token="tok", ca_cert="/tmp/unused.crt"
    )
    return client, calls


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://k8s/lease", code, "err", http.client.HTTPMessage(), None
    )


def test_get_maps_to_get_request(monkeypatch):
    client, calls = _install(monkeypatch, response=FakeResponse({"ok": 1}))

    result = client.get("linx", "jobs-worker")

    assert result == {"ok": 1}
    request = calls[0]
    assert request.get_method() == "GET"
    assert request.full_url == (
        "https://k8s/apis/coordination.k8s.io/v1/namespaces/"
        "linx/leases/jobs-worker"
    )
    assert request.get_header("Authorization") == "Bearer tok"


def test_get_returns_none_on_404(monkeypatch):
    client, _ = _install(monkeypatch, error=_http_error(404))

    assert client.get("linx", "jobs-worker") is None


def test_create_posts_body(monkeypatch):
    body = {"metadata": {"name": "jobs-worker"}}
    client, calls = _install(
        monkeypatch,
        response=FakeResponse({"spec": {"holderIdentity": "pod-0"}}),
    )

    result = client.create("linx", "jobs-worker", body)

    assert result == {"spec": {"holderIdentity": "pod-0"}}
    request = calls[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == body


def test_replace_puts_body(monkeypatch):
    body = {"metadata": {"name": "jobs-worker", "resourceVersion": "2"}}
    client, calls = _install(monkeypatch, response=FakeResponse({}))

    client.replace("linx", "jobs-worker", body)

    request = calls[0]
    assert request.get_method() == "PUT"
    assert json.loads(request.data) == body


def test_replace_maps_409_to_conflict(monkeypatch):
    client, _ = _install(monkeypatch, error=_http_error(409))

    with pytest.raises(LeaseConflictError):
        client.replace("linx", "jobs-worker", {"metadata": {}})


def test_other_http_errors_raise_leader_election_error(monkeypatch):
    client, _ = _install(monkeypatch, error=_http_error(500))

    with pytest.raises(LeaderElectionError):
        client.get("linx", "jobs-worker")


def test_resolve_identity_prefers_env_then_hostname_then_uuid(monkeypatch):
    assert resolve_identity("pod-0") == "pod-0"

    monkeypatch.setenv("HOSTNAME", "pod-1")
    assert resolve_identity("") == "pod-1"

    monkeypatch.delenv("HOSTNAME", raising=False)
    UUID(resolve_identity(""))
