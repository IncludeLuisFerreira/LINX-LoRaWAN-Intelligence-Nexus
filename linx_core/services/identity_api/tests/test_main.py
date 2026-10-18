from fastapi.testclient import TestClient
from linx_shared.core.config import settings
from linx_shared.db.base import get_db
from sqlalchemy.exc import SQLAlchemyError

from identity_api import dependencies as deps_module
from identity_api.config import settings as identity_settings
from identity_api.main import app, create_app

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


def test_health_supports_head():
    _override_db(_OkSession())
    try:
        response = client.head("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_health_degraded_when_db_is_down():
    _override_db(_BrokenSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": False}


def test_health_reports_real_database_as_up():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}


def test_openapi_enabled_outside_production(monkeypatch):
    monkeypatch.setattr(identity_settings, "environment", "development")

    dev_app = create_app()

    assert dev_app.docs_url == "/docs"
    assert dev_app.openapi_url == "/openapi.json"


def test_swagger_disabled_in_production(monkeypatch):
    monkeypatch.setattr(identity_settings, "environment", "production")

    production_app = create_app()
    production_client = TestClient(production_app)

    assert production_app.docs_url is None
    assert production_app.openapi_url is None
    assert production_client.get("/docs").status_code == 404
    assert production_client.get("/openapi.json").status_code == 404


def test_lifespan_closes_cached_chirpstack_client(monkeypatch):
    deps_module._build_chirpstack_client.cache_clear()
    closed: list[bool] = []
    monkeypatch.setattr(
        settings, "service_token", "test-service-token-0123456789abcdef"
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(deps_module, "ChirpStackClient", _FakeClient)
    try:
        deps_module.get_chirpstack_client()

        with TestClient(app):
            pass

        assert closed == [True]
        assert deps_module._build_chirpstack_client.cache_info().currsize == 0
    finally:
        deps_module._build_chirpstack_client.cache_clear()
