import os

# DATABASE_URL é obrigatória no startup (validador em config.py) e a engine é
# construída no import de linx_shared.db.base. Fornecemos um valor de teste
# antes de qualquer import do serviço para não abortar a coleta.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://linx:ci-db-pass@localhost:5432/linx"
)
