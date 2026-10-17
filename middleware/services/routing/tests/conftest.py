import os

# RABBIT_URL passou a ser obrigatória no startup (#210): o default inseguro
# guest:guest foi removido e um validador aborta quando ausente. Fornecemos um
# valor de teste antes dos imports dos módulos do serviço para preservar a
# coleta dos testes já existentes.
os.environ.setdefault(
    "RABBIT_URL", "amqp://linx:ci-rabbit-pass@localhost:5672/%2f"
)
