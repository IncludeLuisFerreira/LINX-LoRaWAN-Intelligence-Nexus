# Deploy k8s com imagens do Docker Hub — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Restrição desta sessão:** commits e push SOMENTE após autorização explícita do usuário. Os passos de commit ficam no plano para referência do executor futuro.

**Goal:** Fazer `identity-api` e `agent-bridge` rodarem no k8s puxando imagens públicas do Docker Hub, com banco configurado, migrations seguras e publicação automática apenas quando os arquivos de cada imagem mudarem.

**Architecture:** Kustomize mantém os manifests atuais como base e adiciona overlays de registry. As imagens são publicadas por um workflow reutilizável do GitHub Actions, chamado por dois workflows com filtros de caminho. O `identity-api` espera o Postgres, aplica migrations sob advisory lock e só então sobe o `uvicorn`; o `agent-bridge` espera o banco antes de iniciar o gRPC.

**Tech Stack:** Kubernetes (k3s/kind), Kustomize, Docker Hub, GitHub Actions, Python 3.12, SQLAlchemy 2, Alembic, PostgreSQL 15, pytest.

**Spec:** `docs/superpowers/specs/2026-11-07-k8s-dockerhub-images-design.md`

## Global Constraints

- Namespace fixo: `linx`. Labels: `app: <nome-do-servico>`.
- Imagens públicas: `includeluisferreira/identity-api` e `includeluisferreira/agent-bridge`.
- Tags: `dev` só de `develop`; `latest` só de `main`; `sha-<short-sha>` em ambos.
- Build sempre `linux/amd64`.
- `imagePullPolicy: Always` enquanto a tag for mutável.
- `DATABASE_URL` do laboratório:
  `postgresql+psycopg://<user>:<pass>@postgres.linx.svc.cluster.local:5432/<db>`.
- Nenhum segredo real commitado; apenas `deploy/k8s/linx-secrets.example.env`.
- Workflows só publicam quando mudarem os paths do serviço ou `linx_core/shared/**`.
- Branch de trabalho: `feat/257-k8s-service-discovery`. PR de tracking: #260.
- Cada bloco implementado deve virar um comentário na PR #260 com arquivos, comandos e resultados reais.
- Commits: Conventional Commits em português com `(#257)`; `git add` arquivo por arquivo.
- Antes de cada commit: `kubectl apply -k deploy/k8s --dry-run=client` e os testes da área tocada devem passar.
- Testes Python: `poetry -C linx_core/shared run pytest ...` e
  `poetry -C linx_core/services/identity_api run pytest ...`.
- Não executar comandos destrutivos no working tree compartilhado.

## Review Focus

1. **`DATABASE_URL` ausente ou inválida**: o serviço deve falhar rápido com mensagem clara, não entrar em loop de 30 tentativas. Teste em Task 1.
2. **Postgres ainda não pronto**: `identity-api` e `agent-bridge` devem esperar o banco no initContainer; readiness do identity deve refletir o banco sem liveness reiniciar pods. Teste/validação em Tasks 3 e 7.
3. **Duas réplicas migrando ao mesmo tempo**: o advisory lock deve serializar as migrations. Teste em Task 2 e validação em Task 7.
4. **Workflow publicando em push irrelevante**: mudanças fora dos paths não devem publicar; `shared` deve publicar as duas imagens. Validação em Task 5.
5. **Tag mutável/arquitetura errada**: `dev` deve ser puxada com `Always` e o build deve ser `linux/amd64`. Validação em Tasks 3, 5 e 7.

---

## File Structure

```text
.github/workflows/
  publish-linx-core-image.yml        # workflow_call reutilizável
  publish-identity-api-image.yml     # caller com paths do identity-api
  publish-agent-bridge-image.yml     # caller com paths do agent-bridge
deploy/k8s/
  identity-api.yaml                  # imagem DH, envFrom, initContainers, probes
  agent-bridge.yaml                  # imagem DH, envFrom, initContainer
  postgres.yaml                      # Recreate + liveness
  linx-secrets.example.env           # chaves e host corretos
  kustomization.yaml                 # base
  README.md                          # runbook
deploy/overlays/
  dockerhub/kustomization.yaml       # overlay explícito
  ecr/kustomization.yaml             # exemplo editável
linx_core/shared/src/linx_shared/db/
  wait.py                            # espera/valida DATABASE_URL
  migration_lock.py                  # advisory lock do Alembic
linx_core/shared/tests/
  test_db_wait.py
  test_migration_lock.py
linx_core/services/identity_api/migrations/env.py
```

---

### Task 1: Utilitário compartilhado de espera do banco

**Files:**
- Create: `linx_core/shared/src/linx_shared/db/wait.py`
- Test: `linx_core/shared/tests/test_db_wait.py`

**Interfaces:**
- Produces: `DatabaseNotReadyError(RuntimeError)`.
- Produces: `wait_for_db(database_url: str | None = None, *, timeout_seconds: float = 60.0, interval_seconds: float = 2.0, connect_timeout: int = 2) -> None`.
- Produces: `python -m linx_shared.db.wait` para uso em initContainer.
- Consumes: `linx_shared.core.config.settings.database_url`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `linx_core/shared/tests/test_db_wait.py`:

```python
import pytest
from sqlalchemy.exc import OperationalError

from linx_shared.db import wait


def test_wait_for_db_rejects_empty_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db("", timeout_seconds=1)


def test_wait_for_db_rejects_invalid_url():
    with pytest.raises(wait.DatabaseNotReadyError, match="DATABASE_URL"):
        wait.wait_for_db("not-a-sqlalchemy-url", timeout_seconds=1)


def test_wait_for_db_retries_until_timeout(monkeypatch):
    calls = []

    def always_fail(url: str, connect_timeout: int) -> None:
        calls.append((url, connect_timeout))
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(wait, "_try_connect", always_fail)

    with pytest.raises(wait.DatabaseNotReadyError, match="after 0.01s"):
        wait.wait_for_db(
            "postgresql+psycopg://u:p@db:5432/db",
            timeout_seconds=0.01,
            interval_seconds=0,
        )

    assert len(calls) >= 2


def test_wait_for_db_returns_on_first_success(monkeypatch):
    calls = []

    def succeed(url: str, connect_timeout: int) -> None:
        calls.append((url, connect_timeout))

    monkeypatch.setattr(wait, "_try_connect", succeed)

    wait.wait_for_db(
        "postgresql+psycopg://u:p@db:5432/db",
        timeout_seconds=1,
        interval_seconds=0,
    )

    assert calls == [("postgresql+psycopg://u:p@db:5432/db", 2)]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `poetry -C linx_core/shared run pytest tests/test_db_wait.py -v`

Expected: FAIL com `ModuleNotFoundError` ou `AttributeError` para `linx_shared.db.wait`.

- [ ] **Step 3: Implementar `wait.py`**

Criar o módulo com:

- `DatabaseNotReadyError(RuntimeError)`.
- `_try_connect(database_url: str, connect_timeout: int) -> None` usando
  `sqlalchemy.create_engine`, `connect_args={"connect_timeout": connect_timeout}`,
  `pool_pre_ping=True`, `SELECT 1` e `engine.dispose()` no `finally`.
- `wait_for_db(...)` que:
  - usa `settings.database_url` somente quando `database_url is None`;
  - rejeita string vazia ou URL inválida com
    `DatabaseNotReadyError("DATABASE_URL ...")`, mesmo que o ambiente tenha
    uma URL configurada;
  - rejeita URL inválida com `DatabaseNotReadyError` antes de tentar conectar;
  - chama `_try_connect` em loop até `timeout_seconds`, dormindo
    `interval_seconds`;
  - em timeout, levanta `DatabaseNotReadyError` com a última `SQLAlchemyError` e
    o tempo no texto (`after {timeout_seconds}s`);
  - retorna `None` no primeiro sucesso.
- Bloco `if __name__ == "__main__": wait_for_db()`.

- [ ] **Step 4: Rodar e ver passar**

Run: `poetry -C linx_core/shared run pytest tests/test_db_wait.py -v`

Expected: PASS (4 testes).

- [ ] **Step 5: Rodar lint/typecheck do shared**

Run:

```bash
poetry -C linx_core/shared run black --check src tests
poetry -C linx_core/shared run isort --check-only src tests
poetry -C linx_core/shared run flake8 src tests
poetry -C linx_core/shared run mypy src tests
```

Expected: todos PASS.

- [ ] **Step 6: Commit (aguardando autorização)**

```bash
git add linx_core/shared/src/linx_shared/db/wait.py linx_core/shared/tests/test_db_wait.py
git commit -m "feat(shared): utilitario de espera do banco para initContainers (#257)"
```

---

### Task 2: Advisory lock para migrations do identity-api

**Files:**
- Create: `linx_core/shared/src/linx_shared/db/migration_lock.py`
- Test: `linx_core/shared/tests/test_migration_lock.py`
- Modify: `linx_core/services/identity_api/migrations/env.py`

**Interfaces:**
- Produces: `MIGRATION_LOCK_KEY: int = 927351`.
- Produces: `acquire_migration_lock(connection) -> None` e
  `release_migration_lock(connection) -> None`.
- Consumes: conexão SQLAlchemy com PostgreSQL.

- [ ] **Step 1: Escrever os testes que falham**

Criar `linx_core/shared/tests/test_migration_lock.py`:

```python
from linx_shared.db.migration_lock import (
    MIGRATION_LOCK_KEY,
    acquire_migration_lock,
    release_migration_lock,
)


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.commits = 0

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))

    def commit(self):
        self.commits += 1


def test_acquire_uses_advisory_lock_and_commits():
    connection = FakeConnection()

    acquire_migration_lock(connection)

    assert "pg_advisory_lock" in connection.executed[0][0]
    assert connection.executed[0][1] == {"key": MIGRATION_LOCK_KEY}
    assert connection.commits == 1


def test_release_uses_advisory_unlock_and_commits():
    connection = FakeConnection()

    release_migration_lock(connection)

    assert "pg_advisory_unlock" in connection.executed[0][0]
    assert connection.executed[0][1] == {"key": MIGRATION_LOCK_KEY}
    assert connection.commits == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `poetry -C linx_core/shared run pytest tests/test_migration_lock.py -v`

Expected: FAIL com `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o helper**

Criar `migration_lock.py`:

```python
from sqlalchemy import text

MIGRATION_LOCK_KEY = 927351


def acquire_migration_lock(connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_lock(:key)"),
        {"key": MIGRATION_LOCK_KEY},
    )
    connection.commit()


def release_migration_lock(connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_unlock(:key)"),
        {"key": MIGRATION_LOCK_KEY},
    )
    connection.commit()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `poetry -C linx_core/shared run pytest tests/test_migration_lock.py -v`

Expected: PASS (2 testes).

- [ ] **Step 5: Integrar no `env.py` do Alembic**

Modificar `run_migrations_online()` em
`linx_core/services/identity_api/migrations/env.py` para usar uma conexão
dedicada ao lock e outra para a migration:

```python
from linx_shared.db.migration_lock import (
    acquire_migration_lock,
    release_migration_lock,
)


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as lock_connection:
        acquire_migration_lock(lock_connection)
        try:
            with connectable.connect() as connection:
                context.configure(
                    connection=connection, target_metadata=target_metadata
                )

                with context.begin_transaction():
                    context.run_migrations()
        finally:
            release_migration_lock(lock_connection)
```

O lock é de sessão e fica na `lock_connection`; a migration usa outra conexão,
evitando conflito de transação com o `context.begin_transaction()`.

- [ ] **Step 6: Rodar testes do shared e do identity-api**

Run:

```bash
poetry -C linx_core/shared run pytest tests/ -v
poetry -C linx_core/services/identity_api run pytest tests/test_startup_config.py tests/test_main.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit (aguardando autorização)**

```bash
git add linx_core/shared/src/linx_shared/db/migration_lock.py \
  linx_core/shared/tests/test_migration_lock.py \
  linx_core/services/identity_api/migrations/env.py
git commit -m "feat(identity-api): serializa migrations do alembic com advisory lock (#257)"
```

---

### Task 3: Manifests com Docker Hub, banco e probes

**Files:**
- Modify: `deploy/k8s/identity-api.yaml`
- Modify: `deploy/k8s/agent-bridge.yaml`
- Modify: `deploy/k8s/postgres.yaml`
- Modify: `deploy/k8s/linx-secrets.example.env`

**Interfaces:**
- Consumes: `linx_shared.db.wait` (Task 1).
- Produces: Pods que puxam `includeluisferreira/identity-api:dev` e
  `includeluisferreira/agent-bridge:dev`.
- Produces: initContainers `wait-for-db` e `migrate`.

- [ ] **Step 1: Atualizar `identity-api.yaml`**

No Deployment `identity-api`:

- Trocar as duas imagens para `includeluisferreira/identity-api:dev`.
- Trocar `imagePullPolicy` para `Always`.
- Manter `envFrom` com `linx-config` e `linx-secrets` nos dois initContainers e
  no container principal.
- Adicionar o initContainer `wait-for-db` antes do `migrate`:

```yaml
- name: wait-for-db
  image: includeluisferreira/identity-api:dev
  imagePullPolicy: Always
  command:
    - python
    - -m
    - linx_shared.db.wait
  envFrom:
    - configMapRef:
        name: linx-config
    - secretRef:
        name: linx-secrets
```

- Manter o initContainer `migrate` com a imagem nova e
  `command: ["python", "-m", "alembic", "-c", "/app/alembic.ini", "upgrade", "head"]`.
- Container principal:
  - `image: includeluisferreira/identity-api:dev`;
  - `imagePullPolicy: Always`;
  - command `python -m uvicorn identity_api.main:app --host 0.0.0.0 --port 8000`;
  - `readinessProbe.httpGet.path: /health`;
  - `livenessProbe.tcpSocket.port: http` (não usar `/health` na liveness).

- [ ] **Step 2: Atualizar `agent-bridge.yaml`**

- Trocar a imagem para `includeluisferreira/agent-bridge:dev`.
- `imagePullPolicy: Always`.
- Manter `envFrom` com ConfigMap e Secret.
- Adicionar initContainer `wait-for-db` com o mesmo comando
  `python -m linx_shared.db.wait` e `envFrom`.
- Manter `readinessProbe` e `livenessProbe` em `tcpSocket` na porta `grpc`.

- [ ] **Step 3: Atualizar `postgres.yaml`**

- Adicionar `strategy: Recreate` no Deployment (PVC `ReadWriteOnce`).
- Adicionar `livenessProbe` com o mesmo `pg_isready` da readiness, com
  `initialDelaySeconds: 30`, `periodSeconds: 10` e `failureThreshold: 6`.

- [ ] **Step 4: Atualizar `linx-secrets.example.env`**

Garantir que o comentário e o exemplo usem o Service correto:

```env
DATABASE_URL=postgresql+psycopg://change-me:change-me@postgres.linx.svc.cluster.local:5432/change-me
```

Manter as chaves `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`SERVICE_TOKEN`, `AGENT_SERVICE_TOKEN`, `CHIRPSTACK_API_TOKEN`,
`RABBITMQ_ADMIN_USER`, `RABBITMQ_ADMIN_PASSWORD`, `RABBITMQ_TENANT_SECRET`.
Atualizar o comentário para dizer que placeholders são rejeitados no startup.

- [ ] **Step 5: Validar manifests**

Run: `kubectl apply -k deploy/k8s --dry-run=client`

Expected: `namespace/linx ... (dry run)`, `deployment.apps/identity-api ...`,
`deployment.apps/agent-bridge ...`, `deployment.apps/postgres ...`, sem erro de
schema.

- [ ] **Step 6: Commit (aguardando autorização)**

```bash
git add deploy/k8s/identity-api.yaml deploy/k8s/agent-bridge.yaml \
  deploy/k8s/postgres.yaml deploy/k8s/linx-secrets.example.env
git commit -m "feat(k8s): imagens do docker hub, initContainers de banco e probes (#257)"
```

---

### Task 4: Overlays de registry

**Files:**
- Create: `deploy/overlays/dockerhub/kustomization.yaml`
- Create: `deploy/overlays/ecr/kustomization.yaml`

**Interfaces:**
- Consumes: base `deploy/k8s`.
- Produces: `kubectl apply -k deploy/overlays/dockerhub` como comando
  explícito do laboratório.
- Produces: exemplo editável de ECR/registry privado.

- [ ] **Step 1: Criar o overlay Docker Hub**

`deploy/overlays/dockerhub/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../k8s
```

- [ ] **Step 2: Criar o exemplo ECR**

`deploy/overlays/ecr/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../k8s
images:
  - name: includeluisferreira/identity-api
    newName: <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/identity-api
    newTag: sha-<SHORT_SHA>
  - name: includeluisferreira/agent-bridge
    newName: <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/agent-bridge
    newTag: sha-<SHORT_SHA>
# Para registry privado, descomente e crie o secret `regcred` no namespace:
# patches:
#   - target:
#       kind: Deployment
#       name: identity-api
#     patch: |-
#       - op: add
#         path: /spec/template/spec/imagePullSecrets
#         value:
#           - name: regcred
```

O README deve deixar claro que este overlay é um exemplo: copie, substitua os
placeholders e só então aplique.

- [ ] **Step 3: Validar os overlays**

Run:

```bash
kubectl kustomize deploy/overlays/dockerhub >/dev/null
kubectl kustomize deploy/overlays/ecr >/dev/null
```

Expected: ambos geram YAML sem erro; o overlay ECR mostra os placeholders
literalmente (Kustomize não interpola variáveis).

- [ ] **Step 4: Commit (aguardando autorização)**

```bash
git add deploy/overlays/dockerhub/kustomization.yaml \
  deploy/overlays/ecr/kustomization.yaml
git commit -m "feat(k8s): overlays de registry docker hub e exemplo ecr (#257)"
```

---

### Task 5: Workflows de publicação por caminho

**Files:**
- Create: `.github/workflows/publish-linx-core-image.yml`
- Create: `.github/workflows/publish-identity-api-image.yml`
- Create: `.github/workflows/publish-agent-bridge-image.yml`

**Interfaces:**
- Consumes: secrets `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN`.
- Produces: imagens `includeluisferreira/identity-api` e
  `includeluisferreira/agent-bridge` com tags `sha-<short>`, `dev` (develop) e
  `latest` (main).

- [ ] **Step 1: Criar o workflow reutilizável**

`.github/workflows/publish-linx-core-image.yml`:

```yaml
name: Publish Linx Core Image

on:
  workflow_call:
    inputs:
      service:
        required: true
        type: string
      dockerfile:
        required: true
        type: string
      repository:
        required: true
        type: string
      context:
        required: false
        type: string
        default: linx_core
    secrets:
      DOCKERHUB_USERNAME:
        required: true
      DOCKERHUB_TOKEN:
        required: true

permissions:
  contents: read

jobs:
  publish:
    runs-on: ubuntu-latest
    concurrency:
      group: publish-${{ inputs.service }}-${{ github.ref }}
      cancel-in-progress: false
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Login no Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Definir tags
        id: tags
        shell: bash
        run: |
          short_sha="${GITHUB_SHA::7}"
          tags="${{ inputs.repository }}:sha-${short_sha}"
          if [[ "$GITHUB_REF" == "refs/heads/develop" ]]; then
            tags+=$'\n'"${{ inputs.repository }}:dev"
          fi
          if [[ "$GITHUB_REF" == "refs/heads/main" ]]; then
            tags+=$'\n'"${{ inputs.repository }}:latest"
          fi
          echo "short_sha=${short_sha}" >> "$GITHUB_OUTPUT"
          echo "tags<<EOF" >> "$GITHUB_OUTPUT"
          echo "$tags" >> "$GITHUB_OUTPUT"
          echo "EOF" >> "$GITHUB_OUTPUT"

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build e push
        uses: docker/build-push-action@v6
        with:
          context: ${{ inputs.context }}
          file: ${{ inputs.dockerfile }}
          platforms: linux/amd64
          push: true
          tags: ${{ steps.tags.outputs.tags }}
          labels: |
            org.opencontainers.image.title=${{ inputs.service }}
            org.opencontainers.image.source=https://github.com/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}

      - name: Validar manifesto publicado
        shell: bash
        run: |
          docker manifest inspect \
            "${{ inputs.repository }}:sha-${{ steps.tags.outputs.short_sha }}" >/dev/null
```

- [ ] **Step 2: Criar o caller do identity-api**

`.github/workflows/publish-identity-api-image.yml`:

```yaml
name: Publish Identity API Image

on:
  push:
    branches:
      - develop
      - main
    paths:
      - "linx_core/services/identity_api/**"
      - "linx_core/shared/**"
      - "linx_core/alembic.ini"
      - ".github/workflows/publish-identity-api-image.yml"
      - ".github/workflows/publish-linx-core-image.yml"
  workflow_dispatch:

jobs:
  publish:
    uses: ./.github/workflows/publish-linx-core-image.yml
    with:
      service: identity_api
      dockerfile: services/identity_api/Dockerfile
      repository: includeluisferreira/identity-api
      context: linx_core
    secrets: inherit
```

- [ ] **Step 3: Criar o caller do agent-bridge**

`.github/workflows/publish-agent-bridge-image.yml`:

```yaml
name: Publish Agent Bridge Image

on:
  push:
    branches:
      - develop
      - main
    paths:
      - "linx_core/services/agent_bridge/**"
      - "linx_core/shared/**"
      - ".github/workflows/publish-agent-bridge-image.yml"
      - ".github/workflows/publish-linx-core-image.yml"
  workflow_dispatch:

jobs:
  publish:
    uses: ./.github/workflows/publish-linx-core-image.yml
    with:
      service: agent_bridge
      dockerfile: services/agent_bridge/Dockerfile
      repository: includeluisferreira/agent-bridge
      context: linx_core
    secrets: inherit
```

- [ ] **Step 4: Validar YAML e filtros**

Run:

```bash
python3 - <<'PY'
import pathlib, yaml
for path in pathlib.Path(".github/workflows").glob("publish-*-image.yml"):
    data = yaml.safe_load(path.read_text())
    assert data
    print(path, "ok")
PY
```

Expected: os três arquivos parseiam sem erro.

Conferir manualmente a matriz de paths:

| Mudança | identity | agent |
| --- | --- | --- |
| `linx_core/services/identity_api/**` | publica | não |
| `linx_core/services/agent_bridge/**` | não | publica |
| `linx_core/shared/**` | publica | publica |
| `docs/**` | não | não |

- [ ] **Step 5: Validar actionlint se disponível**

Run (opcional, se Docker disponível):

```bash
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest
```

Expected: sem erros. Se não houver rede/Docker, registrar a limitação no
comentário da PR.

- [ ] **Step 6: Commit (aguardando autorização)**

```bash
git add .github/workflows/publish-linx-core-image.yml \
  .github/workflows/publish-identity-api-image.yml \
  .github/workflows/publish-agent-bridge-image.yml
git commit -m "ci: publica imagens do linx core apenas quando seus arquivos mudam (#257)"
```

---

### Task 6: Runbook do README

**Files:**
- Modify: `deploy/k8s/README.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: runbook reproduzível para laboratório e AWS/empresa.

- [ ] **Step 1: Reescrever as seções de build/import**

Substituir o fluxo padrão de build/import local por:

1. Docker Hub: imagens públicas e tags.
2. Pull automático pelo cluster; nenhum `ctr images import` no caminho padrão.
3. Build local opcional com `--platform linux/amd64` para debug.
4. Fallback offline com `docker save | ctr images import` apenas quando não
   houver acesso ao registry, deixando claro que não é o fluxo normal.

- [ ] **Step 2: Documentar Secret e banco**

Incluir:

- cópia de `linx-secrets.example.env` para `linx-secrets.env`;
- host `postgres.linx.svc.cluster.local`;
- criação idempotente do Secret;
- aviso de que placeholders são rejeitados;
- como apontar `DATABASE_URL` para RDS/banco externo sem alterar manifests.

- [ ] **Step 3: Documentar migrations e probes**

Explicar:

- initContainer `wait-for-db`;
- initContainer `migrate`;
- advisory lock e por que ele evita race com `replicas: 2`;
- liveness `tcpSocket` e readiness `/health` (banco fora não reinicia pods).

- [ ] **Step 4: Documentar overlays e workflows**

Incluir:

- `kubectl apply -k deploy/k8s` (Docker Hub);
- `kubectl apply -k deploy/overlays/dockerhub`;
- exemplo ECR (copiar/editar placeholders);
- matriz de paths dos workflows;
- tags `dev`, `latest`, `sha-*`;
- secrets `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`;
- rollback por tag/digest e `kubectl rollout undo`.

- [ ] **Step 5: Validar comandos do README**

Executar pelo menos:

```bash
kubectl apply -k deploy/k8s --dry-run=client
kubectl kustomize deploy/overlays/dockerhub >/dev/null
kubectl kustomize deploy/overlays/ecr >/dev/null
```

Expected: sem erros.

- [ ] **Step 6: Commit (aguardando autorização)**

```bash
git add deploy/k8s/README.md
git commit -m "docs(k8s): runbook de imagens docker hub, migrations e overlays (#257)"
```

---

### Task 7: Validação ponta a ponta no kind/k3s

**Files:**
- Nenhum arquivo novo; usa o cluster e os manifests das Tasks 3–6.

**Interfaces:**
- Consumes: imagens publicadas no Docker Hub e Secret `linx-secrets`.
- Produces: evidência real para comentar na PR #260.

- [ ] **Step 1: Garantir repositórios públicos no Docker Hub**

- `includeluisferreira/identity-api` já existe.
- Criar/confirmar `includeluisferreira/agent-bridge` como público.
- Confirmar que o token em `DOCKERHUB_TOKEN` tem escrita nos dois repositórios.

- [ ] **Step 2: Publicar as imagens**

Após autorização de push, disparar os workflows manualmente
(`workflow_dispatch`) ou fazer o push que altere os paths correspondentes.
Confirmar:

```bash
docker manifest inspect includeluisferreira/identity-api:dev
docker manifest inspect includeluisferreira/agent-bridge:dev
```

Expected: ambos `linux/amd64`.

- [ ] **Step 3: Criar namespace/Secret e aplicar**

```bash
kubectl apply -f deploy/k8s/namespace.yaml

cp deploy/k8s/linx-secrets.example.env deploy/k8s/linx-secrets.env
# editar com credenciais reais; DATABASE_URL deve apontar para postgres.linx.svc.cluster.local

kubectl create secret generic linx-secrets -n linx \
  --from-env-file=deploy/k8s/linx-secrets.env \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k deploy/k8s
```

- [ ] **Step 4: Verificar pull do Docker Hub e pods**

```bash
kubectl -n linx get pods -o wide
kubectl -n linx describe pod -l app=identity-api | grep -A3 "Events:"
kubectl -n linx describe pod -l app=agent-bridge | grep -A3 "Events:"
```

Expected:

- 2x `identity-api`, 2x `agent-bridge`, 1x `postgres` `Running`.
- Eventos mostram `Pulling "docker.io/includeluisferreira/identity-api..."` e
  `Pulling "docker.io/includeluisferreira/agent-bridge..."`.
- Nenhum evento de `ErrImagePull`/`ImagePullBackOff`.

- [ ] **Step 5: Verificar migrations e health**

```bash
kubectl -n linx logs deploy/identity-api -c wait-for-db --tail=20
kubectl -n linx logs deploy/identity-api -c migrate --tail=40
kubectl -n linx port-forward svc/identity-api 8000:8000 &
curl -fsS http://localhost:8000/health
```

Expected:

- `wait-for-db` termina sem loop.
- `migrate` aplica `upgrade head` uma vez.
- `/health` retorna `{"status":"ok","db":true}`.

- [ ] **Step 6: Testar race de migrations**

```bash
kubectl -n linx rollout restart deployment/identity-api
kubectl -n linx logs -l app=identity-api -c migrate --tail=40
```

Expected: uma réplica aplica a migration; a outra espera o lock e não falha com
conflito de `alembic_version`.

- [ ] **Step 7: Testar banco fora sem reiniciar pods**

```bash
kubectl -n linx scale deployment/postgres --replicas=0
kubectl -n linx get pods -l app=identity-api
kubectl -n linx get endpoints identity-api
kubectl -n linx scale deployment/postgres --replicas=1
```

Expected: pods do identity continuam `Running`, mas saem dos endpoints/readiness;
não há restart em loop por causa do banco.

- [ ] **Step 8: Comentar na PR #260**

```bash
gh pr comment 260 --body "Implementado: imagens Docker Hub + wait-for-db + advisory lock + workflows por path. Validações: <colar resultados reais>."
```

O comentário deve listar arquivos alterados, comandos executados e saída
relevante. Não declarar sucesso de workflow sem o run real do GitHub Actions.

---

## Self-Review

- **Cobertura do spec:** imagens Docker Hub (Tasks 3–5), overlays (Task 4),
  banco/segredos (Task 3), migrations seguras (Tasks 1–2 + 7), workflows por
  caminho (Task 5), runbook (Task 6), validação (Task 7). Sem gaps.
- **Passos:** cada passo tem um comando ou uma decisão única. Os corpos de
  código aparecem apenas onde o valor exato é o deliverable (helpers, YAML,
  workflows).
- **Consistência de tipos/nomes:** `wait_for_db`, `DatabaseNotReadyError`,
  `MIGRATION_LOCK_KEY`, `acquire_migration_lock`,
  `release_migration_lock`, `wait-for-db`, `migrate` usados de forma idêntica
  nas tasks.
- **Review Focus:** os cinco itens têm teste ou validação na task dona.
- **Proporção:** o plano descreve decisões e valores; não transcreve a
  implementação inteira dos manifests.
