"""Testes de integracao e compatibilidade para o router de ingestao."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from agent.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db_pool():
    """Garante que o pool de banco esteja
    mockado em cada teste deste modulo."""
    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock(return_value="INSERT 0 1")
    app.state.db_pool = mock_pool
    yield
    # Limpeza/restauração se necessário
    app.state.db_pool = None


def test_ingest_returns_201_on_valid_payload():
    """Valida que o endpoint aceita o payload e persiste com sucesso."""
    response = client.post(
        "/ingest", json={"dev_eui": "dev1", "payload": {"t": 20}}
    )
    assert response.status_code == 201
    assert response.json() == {"ok": True}


def test_ingest_invalid_payload_returns_422():
    """Valida que campos obrigatorios ausentes resultam em 422."""
    response = client.post("/ingest", json={"dev_eui": "dev1"})
    assert response.status_code == 422


def test_ingest_empty_dev_eui_returns_422():
    """Valida rejeicao de dev_eui vazio."""
    response = client.post(
        "/ingest", json={"dev_eui": "", "payload": {"t": 20}}
    )
    assert response.status_code == 422
