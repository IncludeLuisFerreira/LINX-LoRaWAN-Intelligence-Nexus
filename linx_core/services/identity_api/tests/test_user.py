from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from linx_shared.core.config import settings as shared_settings
from linx_shared.db.base import engine, get_db
from linx_shared.models.user import User
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from identity_api.main import app
from identity_api.routes.user import password_hasher

client = TestClient(app)

TOKEN = "test-service-token"
AUTH = {"X-Service-Token": TOKEN}


@pytest.fixture(autouse=True)
def service_token(monkeypatch) -> None:
    monkeypatch.setattr(shared_settings, "service_token", TOKEN)


@pytest.fixture(autouse=True)
def db_connection() -> Generator[Connection, None, None]:
    """Isola cada teste em uma transação revertida ao final."""
    connection = engine.connect()
    transaction = connection.begin()

    def override_get_db() -> Generator[Session, None, None]:
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield connection
    app.dependency_overrides.pop(get_db, None)
    transaction.rollback()
    connection.close()


def _create_user(
    email: str = "user@example.com",
    password: str = "secret12345",
    note: str | None = "nota",
) -> dict:
    response = client.post(
        "/api/v1/user/",
        json={"email": email, "password": password, "note": note},
        headers=AUTH,
    )
    assert response.status_code == 201
    return response.json()


def _stored_hash(connection: Connection, email: str) -> str:
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint"
    )
    try:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None
        return user.password_hash
    finally:
        session.close()


def test_missing_token_returns_401():
    response = client.get("/api/v1/user")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid service token"}


def test_wrong_token_returns_401():
    response = client.get("/api/v1/user", headers={"X-Service-Token": "nope"})

    assert response.status_code == 401


def test_unconfigured_token_returns_503(monkeypatch):
    monkeypatch.setattr(shared_settings, "service_token", "")

    response = client.get("/api/v1/user", headers=AUTH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service token is not configured"}


def test_create_user_returns_201_without_password_hash():
    payload = {
        "email": "novo@example.com",
        "password": "secret12345",
        "note": "primeiro",
    }

    response = client.post("/api/v1/user/", json=payload, headers=AUTH)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "novo@example.com"
    assert data["note"] == "primeiro"
    assert data["is_active"] is True
    assert data["is_admin"] is False
    assert data["email_verified"] is False
    assert "password" not in data
    assert "password_hash" not in data
    assert (
        response.headers["Location"]
        == f"http://testserver/api/v1/user/{data['id']}"
    )


def test_create_user_normalizes_email_to_lowercase():
    response = client.post(
        "/api/v1/user/",
        json={"email": "  MixedCase@Example.COM ", "password": "secret12345"},
        headers=AUTH,
    )

    assert response.status_code == 201
    assert response.json()["email"] == "mixedcase@example.com"


def test_create_user_stores_argon2_hash(db_connection):
    _create_user(email="hash@example.com", password="secret12345")

    stored = _stored_hash(db_connection, "hash@example.com")

    assert stored != "secret12345"
    assert stored.startswith("$argon2")
    assert password_hasher.verify(stored, "secret12345")


def test_create_duplicate_email_is_case_insensitive_returns_409():
    _create_user(email="Dup@Example.com")

    response = client.post(
        "/api/v1/user/",
        json={"email": "dup@example.com", "password": "secret12345"},
        headers=AUTH,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered!"}


def test_create_user_with_short_password_returns_422():
    response = client.post(
        "/api/v1/user/",
        json={"email": "short@example.com", "password": "123"},
        headers=AUTH,
    )

    assert response.status_code == 422


def test_list_users_respects_pagination():
    first = _create_user(email="a@example.com")
    second = _create_user(email="b@example.com")

    response = client.get(
        "/api/v1/user", params={"skip": 0, "limit": 100}, headers=AUTH
    )

    assert response.status_code == 200
    data = response.json()
    ids = {user["id"] for user in data}
    assert first["id"] in ids
    assert second["id"] in ids


def test_get_user_returns_200():
    created = _create_user(email="get@example.com")

    response = client.get(f"/api/v1/user/{created['id']}", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["email"] == "get@example.com"


def test_get_non_existent_user_returns_404():
    response = client.get(f"/api/v1/user/{uuid4()}", headers=AUTH)

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found!"}


def test_patch_user_updates_fields_rehashes_password(db_connection):
    created = _create_user(email="patch@example.com")

    response = client.patch(
        f"/api/v1/user/{created['id']}",
        json={
            "password": "newsecret123",
            "note": "atualizado",
            "is_active": False,
        },
        headers=AUTH,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["note"] == "atualizado"
    assert data["is_active"] is False

    stored = _stored_hash(db_connection, "patch@example.com")
    assert password_hasher.verify(stored, "newsecret123")


def test_patch_non_existent_user_returns_404():
    response = client.patch(
        f"/api/v1/user/{uuid4()}",
        json={"note": "x"},
        headers=AUTH,
    )

    assert response.status_code == 404


def test_delete_user_removes_it():
    created = _create_user(email="del@example.com")

    response = client.delete(f"/api/v1/user/{created['id']}", headers=AUTH)

    assert response.status_code == 204

    follow_up = client.get(f"/api/v1/user/{created['id']}", headers=AUTH)
    assert follow_up.status_code == 404


def test_delete_non_existent_user_returns_404():
    response = client.delete(f"/api/v1/user/{uuid4()}", headers=AUTH)

    assert response.status_code == 404
