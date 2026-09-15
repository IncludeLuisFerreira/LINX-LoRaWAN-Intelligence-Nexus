import pytest


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch):
    """Garante variáveis de ambiente obrigatórias durante os testes."""
    monkeypatch.setenv("APP_ID", "test-app-id")
    monkeypatch.setenv("SAAS_GRPC_HOST", "localhost:50051")
