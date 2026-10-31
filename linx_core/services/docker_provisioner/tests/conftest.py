import os

# O Settings do provisioner herda `SERVICE_TOKEN` da biblioteca compartilhada.
# Definir antes da importação evita que o startup de testes dependa do .env.
os.environ.setdefault("SERVICE_TOKEN", "test-service-token-0123456789abcdef")
