import pytest


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch):
    """Garante variáveis de ambiente mínimas durante os testes."""
    monkeypatch.setenv("SAAS_GRPC_HOST", "localhost:50051")
    # mTLS (#82): não herdar credenciais do ambiente do desenvolvedor/CI.
    for name in (
        "GRPC_CA_CERT_PATH",
        "GRPC_CLIENT_CERT_PATH",
        "GRPC_CLIENT_KEY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
