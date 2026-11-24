import os

import pytest

# DATABASE_URL é obrigatória no startup (validador em config.py) e a engine é
# construída no import de linx_shared.db.base. Fornecemos um valor de teste
# antes de qualquer import do serviço para não abortar a coleta.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://linx:ci-db-pass@localhost:5432/linx"
)


@pytest.fixture(autouse=True)
def clear_grpc_tls_settings(monkeypatch):
    """Isola os testes de certificados do ambiente do desenvolvedor."""
    from agent_bridge.config import settings

    for name in (
        "grpc_ca_cert_path",
        "grpc_cert_chain_path",
        "grpc_private_key_path",
    ):
        monkeypatch.setattr(settings, name, "")
