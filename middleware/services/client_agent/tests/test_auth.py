import time
from collections.abc import Generator
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from starlette.testclient import TestClient

from agent.main import app

ME_URL = "/api/v1/agent/me"


def _private_pem(key: rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture(scope="module")
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    )
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return _private_pem(private_key), public_pem


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, rsa_keys: tuple[str, str]
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("JWT_PUBLIC_KEY", rsa_keys[1])
    with patch("agent.main.SaasGrpcClient") as saas_client:
        saas_client.return_value.check_connectivity.return_value = True
        with TestClient(app) as test_client:
            yield test_client


def test_valid_token_is_accepted(
    client: TestClient, rsa_keys: tuple[str, str]
) -> None:
    private_pem, _ = rsa_keys
    token = jwt.encode(
        {"sub": "alice", "roles": ["admin"]}, private_pem, algorithm="RS256"
    )

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"sub": "alice", "roles": ["admin"]}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Token abc"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
    ],
)
def test_missing_or_malformed_authorization_returns_401(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.get(ME_URL, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_token_signed_by_another_key_returns_401(client: TestClient) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {"sub": "mallory"}, _private_pem(other_key), algorithm="RS256"
    )

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_expired_token_returns_401(
    client: TestClient, rsa_keys: tuple[str, str]
) -> None:
    private_pem, _ = rsa_keys
    token = jwt.encode(
        {"sub": "alice", "exp": int(time.time()) - 60},
        private_pem,
        algorithm="RS256",
    )

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_with_wrong_algorithm_returns_401(client: TestClient) -> None:
    token = jwt.encode({"sub": "alice"}, "secret", algorithm="HS256")

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_public_key_with_escaped_newlines_is_supported(
    monkeypatch: pytest.MonkeyPatch, rsa_keys: tuple[str, str]
) -> None:
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("JWT_PUBLIC_KEY", public_pem.replace("\n", "\\n"))
    token = jwt.encode({"sub": "alice"}, private_pem, algorithm="RS256")

    with patch("agent.main.SaasGrpcClient") as saas_client:
        saas_client.return_value.check_connectivity.return_value = True
        with TestClient(app) as test_client:
            response = test_client.get(
                ME_URL, headers={"Authorization": f"Bearer {token}"}
            )

    assert response.status_code == 200


def test_request_returns_401_when_public_key_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, rsa_keys: tuple[str, str]
) -> None:
    monkeypatch.delenv("JWT_PUBLIC_KEY", raising=False)
    token = jwt.encode({"sub": "alice"}, rsa_keys[0], algorithm="RS256")

    with patch("agent.main.SaasGrpcClient") as saas_client:
        saas_client.return_value.check_connectivity.return_value = True
        with TestClient(app) as test_client:
            response = test_client.get(
                ME_URL, headers={"Authorization": f"Bearer {token}"}
            )

    assert response.status_code == 401


def test_health_remains_public(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
