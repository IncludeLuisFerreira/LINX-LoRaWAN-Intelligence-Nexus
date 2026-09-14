import json
from pathlib import Path

from fastapi.testclient import TestClient

from linx.main import app

client = TestClient(app)

STUB_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi-stub.json"


def _openapi() -> dict:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_openapi_exposes_tenant_crud():
    paths = _openapi()["paths"]

    assert "get" in paths["/api/v1/tenant"]
    assert "post" in paths["/api/v1/tenant/"]
    assert {"get", "patch", "delete"} <= set(
        paths["/api/v1/tenant/{tenant_id}"]
    )


def test_openapi_exposes_applications_crud():
    paths = _openapi()["paths"]

    assert {"get", "post"} <= set(
        paths["/api/v1/tenant/{tenant_id}/applications"]
    )
    assert {"get", "patch", "delete"} <= set(
        paths["/api/v1/tenant/{tenant_id}/applications/{application_id}"]
    )


def test_openapi_schemas_have_id_uuid_and_name():
    schemas = _openapi()["components"]["schemas"]

    for schema_name in ("TenantResponse", "ApplicationResponse"):
        properties = schemas[schema_name]["properties"]
        assert properties["id"]["type"] == "string"
        assert properties["id"]["format"] == "uuid"
        assert "name" in properties


def test_openapi_stub_file_matches_live_spec():
    stub = json.loads(STUB_PATH.read_text())

    assert stub == app.openapi()
