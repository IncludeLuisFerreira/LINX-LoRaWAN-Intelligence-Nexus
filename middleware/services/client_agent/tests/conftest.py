import pytest


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch):
    """Garante variáveis de ambiente mínimas durante os testes."""
    monkeypatch.setenv("SAAS_GRPC_HOST", "localhost:50051")
