from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from linx.db.base import get_db
from linx.main import app

client = TestClient(app)


class _OkSession:
    def execute(self, *args, **kwargs):
        return None


class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise SQLAlchemyError("banco indisponível")


def _override_db(session) -> None:
    app.dependency_overrides[get_db] = lambda: session


def test_health_ok_when_db_and_grpc_are_up(monkeypatch):
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: True)
    _override_db(_OkSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "grpc": True}


def test_health_degraded_when_grpc_is_down(monkeypatch):
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: False)
    _override_db(_OkSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "db": True,
        "grpc": False,
    }


def test_health_degraded_when_db_is_down(monkeypatch):
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: True)
    _override_db(_BrokenSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "db": False,
        "grpc": True,
    }


def test_home_html_response():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
