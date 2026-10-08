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
from identity_api.security import password_hasher

client = TestClient(app)

TOKEN = "test-service-token-0123456789abcdef"
AUTH = {"X-Service-Token": TOKEN}
BASE = "/api/v1/user"


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
        BASE,
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
    response = client.get(BASE)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid service token"}


def test_wrong_token_returns_401():
    response = client.get(BASE, headers={"X-Service-Token": "nope"})

    assert response.status_code == 401


def test_unconfigured_token_returns_503(monkeypatch):
    monkeypatch.setattr(shared_settings, "service_token", "")

    response = client.get(BASE, headers=AUTH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service token is not configured"}


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", BASE, {"email": "x@example.com", "password": "secret12345"}),
        ("get", BASE, None),
        ("get", f"{BASE}/{{user_id}}", None),
        ("patch", f"{BASE}/{{user_id}}", {"note": "x"}),
        ("delete", f"{BASE}/{{user_id}}", None),
    ],
)
def test_all_endpoints_require_token(method, path, json_body):
    url = path.format(user_id=uuid4())
    kwargs = {"json": json_body} if json_body is not None else {}

    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 401


def test_startup_rejects_placeholder_token(monkeypatch):
    monkeypatch.setattr(shared_settings, "service_token", "changeme")

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_startup_rejects_short_token(monkeypatch):
    monkeypatch.setattr(shared_settings, "service_token", "too-short")

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_startup_accepts_valid_token(monkeypatch):
    monkeypatch.setattr(shared_settings, "service_token", TOKEN)

    with TestClient(app):
        pass


def test_create_user_returns_201_without_password_hash():
    payload = {
        "email": "novo@example.com",
        "password": "secret12345",
        "note": "primeiro",
    }

    response = client.post(BASE, json=payload, headers=AUTH)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "novo@example.com"
    assert data["note"] == "primeiro"
    assert data["is_active"] is True
    assert data["is_admin"] is False
    assert data["email_verified"] is False
    assert "password" not in data
    assert "password_hash" not in data
    assert response.headers["Location"] == f"{BASE}/{data['id']}"


def test_create_user_normalizes_email_to_lowercase():
    response = client.post(
        BASE,
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
        BASE,
        json={"email": "dup@example.com", "password": "secret12345"},
        headers=AUTH,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered!"}


def test_create_user_with_short_password_returns_422():
    response = client.post(
        BASE,
        json={"email": "short@example.com", "password": "123"},
        headers=AUTH,
    )

    assert response.status_code == 422


def test_list_users_limit_and_skip():
    created = [_create_user(email=f"page{i}@example.com") for i in range(3)]

    first_page = client.get(BASE, params={"skip": 0, "limit": 1}, headers=AUTH)
    second_page = client.get(
        BASE, params={"skip": 1, "limit": 1}, headers=AUTH
    )

    assert first_page.status_code == 200
    assert len(first_page.json()) == 1
    assert second_page.status_code == 200
    assert len(second_page.json()) == 1
    assert first_page.json()[0]["id"] != second_page.json()[0]["id"]

    all_ids = {
        user["id"]
        for user in client.get(
            BASE, params={"limit": 100}, headers=AUTH
        ).json()
    }
    assert {user["id"] for user in created} <= all_ids


@pytest.mark.parametrize(
    "params",
    [{"limit": 101}, {"limit": 0}, {"skip": -1}],
)
def test_list_users_rejects_invalid_pagination(params):
    response = client.get(BASE, params=params, headers=AUTH)

    assert response.status_code == 422


def test_get_user_with_invalid_uuid_returns_422():
    response = client.get(f"{BASE}/not-a-uuid", headers=AUTH)

    assert response.status_code == 422


def test_get_user_returns_200():
    created = _create_user(email="get@example.com")

    response = client.get(f"{BASE}/{created['id']}", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["email"] == "get@example.com"


def test_get_non_existent_user_returns_404():
    response = client.get(f"{BASE}/{uuid4()}", headers=AUTH)

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found!"}


def test_patch_user_updates_fields_rehashes_password(db_connection):
    created = _create_user(email="patch@example.com")

    response = client.patch(
        f"{BASE}/{created['id']}",
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


def test_patch_user_normalizes_email():
    created = _create_user(email="patch-norm@example.com")

    response = client.patch(
        f"{BASE}/{created['id']}",
        json={"email": "  Upper@Example.COM "},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["email"] == "upper@example.com"


def test_patch_user_email_conflict_returns_409():
    first = _create_user(email="conflict-a@example.com")
    second = _create_user(email="conflict-b@example.com")

    response = client.patch(
        f"{BASE}/{second['id']}",
        json={"email": first["email"]},
        headers=AUTH,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered!"}


def test_patch_user_rejects_unknown_fields():
    created = _create_user(email="patch-extra@example.com")

    response = client.patch(
        f"{BASE}/{created['id']}",
        json={"is_admin": True},
        headers=AUTH,
    )

    assert response.status_code == 422


def test_patch_non_existent_user_returns_404():
    response = client.patch(
        f"{BASE}/{uuid4()}",
        json={"note": "x"},
        headers=AUTH,
    )

    assert response.status_code == 404


def test_delete_user_deactivates_it():
    created = _create_user(email="del@example.com")

    response = client.delete(f"{BASE}/{created['id']}", headers=AUTH)

    assert response.status_code == 204

    follow_up = client.get(f"{BASE}/{created['id']}", headers=AUTH)
    assert follow_up.status_code == 200
    assert follow_up.json()["is_active"] is False


def test_delete_non_existent_user_returns_404():
    response = client.delete(f"{BASE}/{uuid4()}", headers=AUTH)

    assert response.status_code == 404
