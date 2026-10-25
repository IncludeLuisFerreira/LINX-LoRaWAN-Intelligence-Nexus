from fastapi.testclient import TestClient

from tenant_app.app import create_app

TOKEN = "tenant-service-token-0123456789abcdef"
APP_ID = "3d7f1a8e-3f4b-4f0a-9b7c-2e1d9a8b7c6d"
MQTT_TOPIC = f"application/{APP_ID}/device/+/event/up"
DB_PASSWORD = "super-secret-db-password"


def _client(monkeypatch, *, service_token: str = TOKEN) -> TestClient:
    monkeypatch.setenv("APP_ID", APP_ID)
    monkeypatch.setenv("MQTT_TOPIC", MQTT_TOPIC)
    monkeypatch.setenv("DB_PASSWORD", DB_PASSWORD)
    monkeypatch.setenv("SERVICE_TOKEN", service_token)
    return TestClient(create_app())


def test_health_is_public(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_id": APP_ID}


def test_info_requires_service_token(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/info")

    assert response.status_code == 401


def test_info_rejects_wrong_service_token(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/info", headers={"X-Service-Token": "wrong-token"})

    assert response.status_code == 401


def test_info_returns_public_fields_with_valid_token(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/info", headers={"X-Service-Token": TOKEN})

    assert response.status_code == 200
    assert response.json() == {
        "app_id": APP_ID,
        "mqtt_topic": MQTT_TOPIC,
        "db_password_configured": True,
    }
    assert DB_PASSWORD not in response.text


def test_info_returns_503_when_service_token_is_not_configured(
    monkeypatch,
):
    client = _client(monkeypatch, service_token="")

    response = client.get("/info", headers={"X-Service-Token": TOKEN})

    assert response.status_code == 503
