import os

# rabbit_url e db_password agora têm default vazio e são validados no startup
# (#210). Envs de teste garantem que os testes existentes (que instanciam
# ConsumerSettings com apenas alguns campos) continuem construindo o objeto.
os.environ.setdefault(
    "RABBIT_URL", "amqp://tenant:ci-rabbit-pass@localhost:5672/%2f"
)
os.environ.setdefault("DB_PASSWORD", "ci-tenant-db-pass")
os.environ.setdefault("SERVICE_TOKEN", "ci-service-token")
