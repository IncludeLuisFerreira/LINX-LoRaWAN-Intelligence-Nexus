from fastapi.testclient import TestClient
from linx_shared.db.base import get_db
from sqlalchemy.exc import SQLAlchemyError

from identity_api.main import app

client = TestClient(app)


class _OkSession:
    def execute(self, *args, **kwargs):
        return None


class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise SQLAlchemyError("banco indisponível")


def _override_db(session) -> None:
    app.dependency_overrides[get_db] = lambda: session


def test_health_ok_when_db_is_up():
    _override_db(_OkSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}


def test_health_degraded_when_db_is_down():
    _override_db(_BrokenSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": False}


def test_home_html_response():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_health_reports_real_database_as_up():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}
