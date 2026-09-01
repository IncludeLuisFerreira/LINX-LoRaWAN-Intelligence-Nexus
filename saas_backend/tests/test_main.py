from fastapi.testclient import TestClient

from linx.main import app

client = TestClient(app)


def test_read_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_html_response():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
