"""Testes automatizados para o endpoint POST /ingest."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from agent.main import app


@pytest.fixture
def client_with_db() -> TestClient:
    """Retorna TestClient com pool de banco mockado no app.state."""
    mock_pool = MagicMock()
    app.state.db_pool = mock_pool
    return TestClient(app)


def test_ingest_success_full_payload(client_with_db: TestClient) -> None:
    """Valida ingestao bem-sucedida com todos os campos preenchidos."""
    body = {
        "dev_eui": "0004A30B001F1234",
        "payload": {"temperature": 23.5, "humidity": 60.2},
        "rssi": -75,
        "snr": 9.5,
    }
    with patch(
        "agent.routers.ingest.insert_telemetry",
        new_callable=AsyncMock,
    ) as mock_insert:
        response = client_with_db.post("/ingest", json=body)

        assert response.status_code == 201
        assert response.json() == {"ok": True}
        mock_insert.assert_awaited_once_with(
            pool=app.state.db_pool,
            dev_eui="0004A30B001F1234",
            payload={"temperature": 23.5, "humidity": 60.2},
            rssi=-75,
            snr=9.5,
        )


def test_ingest_success_minimal_payload(client_with_db: TestClient) -> None:
    """Valida ingestao bem-sucedida omitindo campos opcionais (rssi/snr)."""
    body = {
        "dev_eui": "AABBCCDDEEFF0011",
        "payload": {"status": "active"},
    }
    with patch(
        "agent.routers.ingest.insert_telemetry",
        new_callable=AsyncMock,
    ) as mock_insert:
        response = client_with_db.post("/ingest", json=body)

        assert response.status_code == 201
        assert response.json() == {"ok": True}
        mock_insert.assert_awaited_once_with(
            pool=app.state.db_pool,
            dev_eui="AABBCCDDEEFF0011",
            payload={"status": "active"},
            rssi=None,
            snr=None,
        )


def test_ingest_missing_dev_eui(client_with_db: TestClient) -> None:
    """Valida rejeicao 422 quando dev_eui nao e informado."""
    body = {"payload": {"temp": 20}}
    response = client_with_db.post("/ingest", json=body)
    assert response.status_code == 422


def test_ingest_empty_dev_eui(client_with_db: TestClient) -> None:
    """Valida rejeicao 422 quando dev_eui e uma string vazia."""
    body = {"dev_eui": "", "payload": {"temp": 20}}
    response = client_with_db.post("/ingest", json=body)
    assert response.status_code == 422


def test_ingest_missing_payload(client_with_db: TestClient) -> None:
    """Valida rejeicao 422 quando o objeto de telemetria nao e informado."""
    body = {"dev_eui": "0004A30B001F1234"}
    response = client_with_db.post("/ingest", json=body)
    assert response.status_code == 422


def test_ingest_database_failure(client_with_db: TestClient) -> None:
    """Valida retorno 500 quando a persistencia lanca excecao."""
    body = {
        "dev_eui": "0004A30B001F1234",
        "payload": {"temp": 25.0},
    }
    with patch(
        "agent.routers.ingest.insert_telemetry",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Falha de conexao com o banco"),
    ):
        response = client_with_db.post("/ingest", json=body)
        assert response.status_code == 500
        assert response.json() == {"detail": "Database insertion error"}


def test_ingest_pool_unavailable() -> None:
    """Valida retorno 500 quando db_pool nao foi configurado no state."""
    app.state.db_pool = None
    client = TestClient(app)
    body = {
        "dev_eui": "0004A30B001F1234",
        "payload": {"temp": 25.0},
    }
    response = client.post("/ingest", json=body)
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Database connection pool unavailable"
    }
