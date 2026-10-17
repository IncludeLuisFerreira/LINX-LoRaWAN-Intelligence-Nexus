import os

# database_url perdeu o default inseguro (#210). A engine em
# linx_shared.db.base é construída no import, então fornecemos um valor de
# teste parseable antes dos imports que a exercitam. A base Settings continua
# sem validador (routing herda dela e não usa banco).
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://linx:ci-db-pass@localhost:5432/linx"
)
