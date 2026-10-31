# Reorganização `linx_core/services` + `middleware/services` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar a migração de `saas_backend`/`client_agent_api` para `linx_core/services/*` e `middleware/services/*`, corrigindo referências e nomenclatura para build, testes, CI e docs consistentes.

**Architecture:** Movimentação de diretórios com `git mv`, seguida de correção de path dependencies (Poetry), Docker/Compose, task-runners/scripts, CI, rename do proto e limpeza de documentação. Sem mudança de lógica de negócio. O serviço `routing` apenas é movido e tem seu path dep corrigido (refatoração adiada).

**Tech Stack:** Python 3.12, Poetry, FastAPI, gRPC (grpcio-tools), Alembic, Docker Compose, GitHub Actions, MkDocs.

**Spec:** `docs/superpowers/specs/2026-10-08-linx-core-services-reorg-design.md`

## Global Constraints

- Python `>=3.12,<4.0`; Poetry `2.4.1` no CI.
- Core build context = raiz de `linx_core/`. Dockerfiles espelham a estrutura do repo dentro da imagem.
- Contexto de build do `routing` = **raiz do repositório** (depende de `linx_core/shared`).
- Nomes-alvo: `linx_core` (projeto raiz), `linx-middleware` (projeto raiz do middleware), `linx-shared`, `linx_agent` (proto/stubs).
- Não reescrever planos/specs históricos em `docs/superpowers/plans/` e `docs/superpowers/specs/` (exceto este plano e o spec citado).
- **Não commitar nada até autorização explícita do usuário.** Todos os passos "Commit" ficam marcados como HOLD.
- Não mover artefatos gerados (`.venv/`, `.mypy_cache/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `__pycache__/`).

## Review Focus

- **Referência remanescente a nomes antigos:** `saas_backend`, `client_agent_api`, `tenant_app_template`, `saas_agent` em arquivos ativos (fora de docs históricos) causam CI/build quebrados. Esperado: zero ocorrências ativas.
- **Path dependency errado:** `../shared` vs `../../shared` vs `../../../linx_core/shared`; um erro faz `poetry install` e Docker falharem.
- **Contexto Docker inconsistente:** `docker-compose.yml` apontando `dockerfile` inexistente ou contexto sem `shared/` quebra o build.
- **Stub gRPC dessincronizado:** imports `saas_agent_pb2` remanescentes após rename causam `ImportError` em runtime/testes.
- **Trigger de CI desatualizado:** `on.paths` sem `linx_core/**`/`middleware/**` faz a pipeline não rodar nos PRs corretos.

---

### Task 1: Reorganizar `middleware/` (mover `routing` e Client Agent)

**Files:**
- Move: `middleware/routing/` → `middleware/services/routing/`
- Move: `middleware/pyproject.toml`, `middleware/src/`, `middleware/tests/`, `middleware/Dockerfile`, `middleware/.flake8`, `middleware/.env.example`, `middleware/README.md`, `middleware/docker-compose.prod.yml` → `middleware/services/client_agent/`
- Create: `middleware/pyproject.toml` (task-runner raiz)

**Interfaces:**
- Produces: estrutura `middleware/services/{client_agent,routing}` para as tasks seguintes.

- [ ] **Step 1: Mover arquivos com `git mv`**

```bash
mkdir -p middleware/services
git mv middleware/routing middleware/services/routing
mkdir -p middleware/services/client_agent
for f in pyproject.toml Dockerfile .flake8 .env.example README.md docker-compose.prod.yml src tests; do
  git mv "middleware/$f" "middleware/services/client_agent/$f"
done
```

- [ ] **Step 2: Criar `middleware/pyproject.toml` (task-runner raiz)**

Conteúdo (espelha o task-runner de `linx_core/pyproject.toml`):

```toml
[project]
name = "linx-middleware"
version = "0.1.0"
description = "Task runner do middleware (client_agent + routing)."
requires-python = ">=3.12,<4.0"

[tool.poetry]
package-mode = false

[dependency-groups]
dev = [
    "taskipy (>=1.14.1,<2.0.0)"
]

[tool.taskipy.tasks]
lint = "poetry -C services/client_agent run task lint && poetry -C services/routing run task lint"
test = "poetry -C services/client_agent run pytest && poetry -C services/routing run pytest"
```

- [ ] **Step 3: Verificar a árvore**

Run:
```bash
find middleware -maxdepth 3 -type d -not -path '*/.venv/*' -not -path '*/.mypy_cache/*' -not -path '*/.pytest_cache/*' -not -path '*/__pycache__/*' | sort
```
Expected: `middleware/services/client_agent` e `middleware/services/routing` presentes; nenhum `middleware/src` ou `middleware/routing` na raiz.

- [ ] **Step 4: Commit (HOLD)**

```bash
git add -A middleware
git commit -m "refactor(middleware): move client_agent e routing para services/"
```
**HOLD — não executar até autorização do usuário.**

---

### Task 2: Corrigir path dependencies (Poetry)

**Files:**
- Modify: `linx_core/services/identity_api/pyproject.toml`
- Modify: `linx_core/services/agent_bridge/pyproject.toml`
- Modify: `middleware/services/routing/pyproject.toml`
- Modify: `middleware/services/client_agent/pyproject.toml` (nome do projeto)

**Interfaces:**
- Produces: dependências resolvíveis via `poetry install` para todas as tasks seguintes.

- [ ] **Step 1: Corrigir `linx_core/services/identity_api/pyproject.toml`**

Trocar a linha do `linx-shared` para:
```toml
linx-shared = { path = "../../shared", develop = true }
```

- [ ] **Step 2: Corrigir `linx_core/services/agent_bridge/pyproject.toml`**

Trocar a linha do `linx-shared` para:
```toml
linx-shared = { path = "../../shared", develop = true }
```

- [ ] **Step 3: Corrigir `middleware/services/routing/pyproject.toml`**

Trocar a linha do `linx-shared` para:
```toml
linx-shared = { path = "../../../linx_core/shared", develop = true }
```

- [ ] **Step 4: Ajustar nome do projeto do Client Agent**

Em `middleware/services/client_agent/pyproject.toml`, alterar:
```toml
name = "client-agent"
```
(Manter `[tool.poetry] packages = [{include="agent", from="src"}]` — o pacote importável segue `agent`.)

- [ ] **Step 5: Verificar resolução dos path deps**

Run:
```bash
poetry -C linx_core/services/identity_api check
poetry -C linx_core/services/agent_bridge check
poetry -C middleware/services/client_agent check
poetry -C middleware/services/routing check
```
Expected: cada comando sem erro de path dependency. (Se `poetry check` não validar paths, usar `poetry -C <pkg> install --dry-run`.)

- [ ] **Step 6: Commit (HOLD)**

```bash
git add linx_core/services/identity_api/pyproject.toml linx_core/services/agent_bridge/pyproject.toml middleware/services/routing/pyproject.toml middleware/services/client_agent/pyproject.toml
git commit -m "fix(packaging): corrige path deps linx-shared e nome do client-agent"
```
**HOLD.**

---

### Task 3: Alembic, task-runners e scripts do core

**Files:**
- Modify: `linx_core/alembic.ini`
- Modify: `linx_core/pyproject.toml`
- Modify: `linx_core/scripts/run.sh`
- Review: `linx_core/scripts/deploy.sh`

**Interfaces:**
- Consumes: estrutura de `services/` da Task 1.
- Produces: comandos de migração/run coerentes para Task 4 e Task 5.

- [ ] **Step 1: Corrigir `linx_core/alembic.ini`**

Alterar:
```ini
script_location = %(here)s/services/identity_api/migrations
```

- [ ] **Step 2: Corrigir `linx_core/pyproject.toml`**

```toml
[project]
name = "linx-core"
version = "0.1.0"
description = "Task runner do Linx Core (identity_api + agent_bridge)."
requires-python = ">=3.12,<4.0"
```
E as tasks:
```toml
migrate = "env -u VIRTUAL_ENV poetry -C services/identity_api run alembic -c ../../alembic.ini upgrade head"
migration = "env -u VIRTUAL_ENV poetry -C services/identity_api run alembic -c ../../alembic.ini revision --autogenerate -m"
test = "env -u VIRTUAL_ENV poetry -C shared run pytest && env -u VIRTUAL_ENV poetry -C services/identity_api run pytest && env -u VIRTUAL_ENV poetry -C services/agent_bridge run pytest"
```

- [ ] **Step 3: Corrigir `linx_core/scripts/run.sh`**

```bash
poetry -C services/identity_api run uvicorn identity_api.main:app --reload &
poetry -C services/agent_bridge run python -m agent_bridge.server &
```

- [ ] **Step 4: Revisar `linx_core/scripts/deploy.sh`**

Ajustar qualquer caminho `identity_api`/`agent_bridge`/`migrations` para o prefixo `services/`.

- [ ] **Step 5: Verificar parse do alembic**

Run:
```bash
poetry -C linx_core/services/identity_api run alembic -c ../../alembic.ini heads
```
Expected: lista revisões sem erro de `script_location`.
(Fallback sem venv: `grep -n "script_location" linx_core/alembic.ini` deve mostrar `services/identity_api/migrations`.)

- [ ] **Step 6: Commit (HOLD)**

```bash
git add linx_core/alembic.ini linx_core/pyproject.toml linx_core/scripts/run.sh linx_core/scripts/deploy.sh
git commit -m "chore(linx_core): aponta alembic, tasks e scripts para services/"
```
**HOLD.**

---

### Task 4: Dockerfiles e Compose

**Files:**
- Modify: `linx_core/docker-compose.yml`
- Modify: `linx_core/services/identity_api/Dockerfile`
- Modify: `linx_core/services/agent_bridge/Dockerfile`
- Modify: `middleware/services/routing/Dockerfile`
- Modify: `middleware/services/client_agent/docker-compose.prod.yml` (se citar caminhos)
- Modify: `deploy/docker-compose.yml`

**Interfaces:**
- Consumes: estrutura de `services/` (Tasks 1–3).

- [ ] **Step 1: Corrigir `linx_core/docker-compose.yml`**

```yaml
  identity_api:
    build:
      context: .
      dockerfile: services/identity_api/Dockerfile
  agent_bridge:
    build:
      context: .
      dockerfile: services/agent_bridge/Dockerfile
```

- [ ] **Step 2: Corrigir `linx_core/services/identity_api/Dockerfile`**

Builder:
```dockerfile
COPY shared ./shared
COPY services/identity_api ./services/identity_api
RUN poetry -C services/identity_api config virtualenvs.in-project true \
    && poetry -C services/identity_api install --without dev --no-interaction --no-ansi
```
Runtime:
```dockerfile
COPY --from=builder /app/shared ./shared
COPY --from=builder /app/services/identity_api ./services/identity_api
COPY alembic.ini ./alembic.ini
COPY services/identity_api/docker-entrypoint.sh ./docker-entrypoint.sh
ENV PATH="/app/services/identity_api/.venv/bin:$PATH" \
    PYTHONPATH=/app/services/identity_api/src:/app/shared/src
```
(`migrations/` já está dentro de `services/identity_api/`, coberto pelo `COPY` acima; `script_location` do alembic resolve em `/app/services/identity_api/migrations`.)

- [ ] **Step 3: Corrigir `linx_core/services/agent_bridge/Dockerfile`**

```dockerfile
COPY shared ./shared
COPY services/agent_bridge ./services/agent_bridge
RUN poetry -C services/agent_bridge config virtualenvs.in-project true \
    && poetry -C services/agent_bridge install --without dev --no-interaction --no-ansi
```
Runtime:
```dockerfile
COPY --from=builder /app/shared ./shared
COPY --from=builder /app/services/agent_bridge ./services/agent_bridge
ENV PATH="/app/services/agent_bridge/.venv/bin:$PATH" \
    PYTHONPATH=/app/services/agent_bridge/src:/app/shared/src
```

- [ ] **Step 4: Corrigir `middleware/services/routing/Dockerfile` (contexto = raiz do repo)**

```dockerfile
COPY linx_core/shared ./shared
COPY middleware/services/routing ./routing
RUN poetry -C routing config virtualenvs.in-project true \
    && poetry -C routing install --without dev --no-interaction --no-ansi
```
Runtime:
```dockerfile
COPY --from=builder /app/shared ./shared
COPY --from=builder /app/routing ./routing
ENV PATH="/app/routing/.venv/bin:$PATH" \
    PYTHONPATH=/app/routing/src:/app/shared/src
```

- [ ] **Step 5: Corrigir `deploy/docker-compose.yml`**

```yaml
  identity_api:
    build:
      context: ../linx_core/.
      dockerfile: services/identity_api/Dockerfile
  agent_bridge:
    build:
      context: ../linx_core/.
      dockerfile: services/agent_bridge/Dockerfile
  client_agent:
    build:
      context: ../middleware/services/client_agent/.
      dockerfile: Dockerfile
  tenant_app:
    build: ../client/.
  routing:
    build:
      context: ../
      dockerfile: middleware/services/routing/Dockerfile
```

- [ ] **Step 6: Verificar sintaxe dos Compose**

Run:
```bash
docker compose -f linx_core/docker-compose.yml config >/dev/null && echo OK-core
docker compose -f deploy/docker-compose.yml config >/dev/null && echo OK-deploy
```
Expected: `OK-core` e `OK-deploy`.

- [ ] **Step 7: Commit (HOLD)**

```bash
git add linx_core/docker-compose.yml linx_core/services/identity_api/Dockerfile linx_core/services/agent_bridge/Dockerfile middleware/services/routing/Dockerfile middleware/services/client_agent/docker-compose.prod.yml deploy/docker-compose.yml
git commit -m "fix(docker): atualiza contextos e Dockerfiles para services/"
```
**HOLD.**

---

### Task 5: CI (GitHub Actions)

**Files:**
- Modify: `.github/workflows/backend-ci.yml`
- Create: `.github/workflows/middleware-ci.yml`
- Delete: `.github/workflows/client-agent-api-ci.yml`

**Interfaces:**
- Consumes: estrutura de `services/` (Tasks 1–3).

- [ ] **Step 1: Corrigir `backend-ci.yml`**

- `on.pull_request.paths` e `on.push.paths`: `"linx_core/**"`.
- `defaults.run.working-directory: linx_core`.
- Matriz lint e test: `package: [shared, services/identity_api, services/agent_bridge]`.
- Instalação de deps do job test:
```yaml
        run: |
          poetry -C shared install
          poetry -C services/identity_api install
          poetry -C services/agent_bridge install
```
- Migrations:
```yaml
        run: poetry -C services/identity_api run alembic -c ../../alembic.ini upgrade head
```

- [ ] **Step 2: Criar `middleware-ci.yml`**

`on.paths`: `"middleware/**"` e o próprio workflow. `defaults.working-directory: middleware`. Jobs de lint/test por pacote `[services/client_agent, services/routing]` usando `poetry -C ${{ matrix.package }} ...`. O CI do Client Agent e do routing compartilha o mesmo workflow.

- [ ] **Step 3: Remover `client-agent-api-ci.yml`**

```bash
git rm .github/workflows/client-agent-api-ci.yml
```

- [ ] **Step 4: Verificar consistência de caminhos**

Run:
```bash
grep -rn "saas_backend\|client_agent_api\|tenant_app_template" .github/workflows || echo "no-stale-refs"
```
Expected: `no-stale-refs`.

- [ ] **Step 5: Commit (HOLD)**

```bash
git add .github/workflows/backend-ci.yml .github/workflows/middleware-ci.yml
git rm .github/workflows/client-agent-api-ci.yml
git commit -m "ci: aponta workflows para linx_core/ e middleware/"
```
**HOLD.**

---

### Task 6: Renomear proto e stubs gRPC

**Files:**
- Move: `proto/saas_agent.proto` → `proto/linx_agent.proto`
- Modify: `scripts/gen_proto.sh`
- Regenerate: `linx_core/shared/src/linx_shared/grpc/linx_agent_pb2{,_grpc}.py`, `middleware/services/client_agent/src/agent/grpc/linx_agent_pb2{,_grpc}.py`, `client/src/tenant/grpc/linx_agent_pb2{,_grpc}.py`
- Modify (imports): `linx_core/services/agent_bridge/src/agent_bridge/server.py`, `linx_core/services/agent_bridge/tests/test_grpc.py`, `client/src/tenant/grpc_client.py`, `client/tests/test_grpc_client.py`, `middleware/services/client_agent/src/agent/grpc_client.py`, `middleware/services/client_agent/tests/test_grpc_client.py`

**Interfaces:**
- Produces: símbolos `linx_agent_pb2`/`linx_agent_pb2_grpc` para todas as camadas que usam o contrato `AgentBridge`.

- [ ] **Step 1: Renomear o proto**

```bash
git mv proto/saas_agent.proto proto/linx_agent.proto
```

- [ ] **Step 2: Atualizar `scripts/gen_proto.sh`**

- Header/comentários: `linx_agent_pb2.py / linx_agent_pb2_grpc.py`, `proto/linx_agent.proto`.
- Destinos:
```bash
gen linx_core/shared linx_core/shared/src/linx_shared/grpc
gen middleware/services/client_agent middleware/services/client_agent/src/agent/grpc
gen client client/src/tenant/grpc
```
- Loop do `sed`:
```bash
for grpc_file in \
  linx_core/shared/src/linx_shared/grpc/linx_agent_pb2_grpc.py \
  middleware/services/client_agent/src/agent/grpc/linx_agent_pb2_grpc.py \
  client/src/tenant/grpc/linx_agent_pb2_grpc.py; do
  sed -i 's/^import linx_agent_pb2 as linx__agent__pb2$/from . import linx_agent_pb2 as linx__agent__pb2/' "$grpc_file"
done
```

- [ ] **Step 3: Remover stubs antigos e regenerar**

Remover apenas os arquivos `*_pb2*.py` (preservar `__init__.py` de cada pacote `grpc/`):

```bash
git rm linx_core/shared/src/linx_shared/grpc/saas_agent_pb2.py \
       linx_core/shared/src/linx_shared/grpc/saas_agent_pb2_grpc.py \
       middleware/services/client_agent/src/agent/grpc/saas_agent_pb2.py \
       middleware/services/client_agent/src/agent/grpc/saas_agent_pb2_grpc.py \
       client/src/tenant/grpc/saas_agent_pb2.py \
       client/src/tenant/grpc/saas_agent_pb2_grpc.py
bash scripts/gen_proto.sh
```
Plan B (se `grpcio-tools` indisponível): `git mv` cada `saas_agent_pb2*` → `linx_agent_pb2*` e editar o interior (`source: saas_agent.proto` → `linx_agent.proto`, `'saas_agent_pb2'` → `'linx_agent_pb2'`, alias `saas__agent__pb2` → `linx__agent__pb2`).

- [ ] **Step 4: Atualizar imports nos consumidores**

Substituir em todos os arquivos listados:
- `saas_agent_pb2` → `linx_agent_pb2`
- `saas_agent_pb2_grpc` → `linx_agent_pb2_grpc`
- strings de `patch("...saas_agent_pb2_grpc....")` → `linx_agent_pb2_grpc`

- [ ] **Step 5: Verificar imports**

Run:
```bash
poetry -C linx_core/services/agent_bridge run python -c "from linx_shared.grpc import linx_agent_pb2, linx_agent_pb2_grpc; print('ok-shared')"
poetry -C middleware/services/client_agent run python -c "from agent.grpc import linx_agent_pb2, linx_agent_pb2_grpc; print('ok-agent')"
poetry -C client run python -c "from tenant.grpc import linx_agent_pb2, linx_agent_pb2_grpc; print('ok-tenant')"
```
Expected: `ok-shared`, `ok-agent`, `ok-tenant`.

- [ ] **Step 6: Commit (HOLD)**

```bash
git add -A proto scripts linx_core middleware/services/client_agent client
git commit -m "refactor(proto): renomeia saas_agent para linx_agent e regenera stubs"
```
**HOLD.**

---

### Task 7: Documentação e nomenclatura

**Files:**
- Modify: `README.md`, `docs/index.md`, `docs/estrutura_de_pastas/estrutura.md`, `docs/comunicacao_entre_servicos.md`, `docs/PRD_PLATAFORMA_IOT.md`, `PRD_PLATAFORMA_IOT.md`, `PROGRESS.md`, `SPRINTS_BACKLOG.md`, `mkdocs.yml`, `linx_core/README.md`, `docs/middleware/README.md`, `docs/client/README.md`, `middleware/services/client_agent/README.md`, `client/README.md`, `proto/README.md`
- Move: `docs/saas_backend/` → `docs/linx_core/`
- Move: `docs/tenant_app_template/` → `docs/client/`

**Interfaces:**
- Consumes: estrutura final das Tasks 1–6.

- [ ] **Step 1: Renomear diretórios de doc**

```bash
git mv docs/saas_backend docs/linx_core
git mv docs/tenant_app_template docs/client
```

- [ ] **Step 2: Atualizar `mkdocs.yml`**

Nav "Módulos do Sistema":
```yaml
      - Linx Core: linx_core/README.md
      - Middleware: middleware/README.md
      - Client (Tenant App): client/README.md
```

- [ ] **Step 3: Atualizar árvore/descrições em `README.md` e `docs/index.md`**

Substituir:
- `saas_backend/` → `linx_core/` (com `services/`)
- `client_agent_api/` → `middleware/` (com `services/client_agent`)
- `tenant_app_template/` → `client/`
- `proto/saas_agent.proto` → `proto/linx_agent.proto`
- "SaaS Backend" → "Linx Core"

- [ ] **Step 4: Atualizar docs de módulo e textos**

- `docs/middleware/README.md`, `middleware/services/client_agent/README.md`: caminhos `src/agent` → `middleware/services/client_agent/src/agent`; `saas_agent_pb2*` → `linx_agent_pb2*`.
- `docs/linx_core/README.md` e `linx_core/README.md`: `cd saas_backend` → `cd linx_core`; paths internos com `services/`; proto renomeado.
- `client/README.md`, `docs/client/README.md`: `saas_agent.proto` → `linx_agent.proto`, referências a `client_agent_api` → `middleware`.
- `proto/README.md`: prefixos `saas_agent` → `linx_agent`; caminhos de stubs atualizados.
- `docs/comunicacao_entre_servicos.md`, `docs/estrutura_de_pastas/estrutura.md`, `docs/PRD_PLATAFORMA_IOT.md`, `PRD_PLATAFORMA_IOT.md`: nomes antigos dos módulos.
- `PROGRESS.md`, `SPRINTS_BACKLOG.md`: menções a `proto/saas_agent.proto`, `saas_backend`, `client_agent_api`, `tenant_app_template`.

- [ ] **Step 5: Verificar ausência de refs antigas ativas**

Run:
```bash
grep -rn "saas_backend\|client_agent_api\|tenant_app_template\|saas_agent" . \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=htmlcov --exclude-dir=.mypy_cache --exclude-dir=.pytest_cache \
  --exclude-dir=__pycache__ \
  | grep -v "docs/superpowers/plans/" | grep -v "docs/superpowers/specs/"
```
Expected: nenhuma linha (fora dos documentos históricos).

- [ ] **Step 6: Buildar docs**

Run: `mkdocs build --strict`
Expected: build sem links quebrados.

- [ ] **Step 7: Commit (HOLD)**

```bash
git add -A README.md docs mkdocs.yml PROGRESS.md SPRINTS_BACKLOG.md PRD_PLATAFORMA_IOT.md linx_core/README.md middleware/services/client_agent/README.md client/README.md proto/README.md
git commit -m "docs: atualiza estrutura, nomenclatura e links pos-reorg"
```
**HOLD.**

---

### Task 8: Verificação final end-to-end

**Files:** nenhum (somente verificação).

**Interfaces:**
- Consumes: todas as tasks anteriores.

- [ ] **Step 1: Instalar e testar cada pacote**

```bash
poetry -C linx_core/shared install && poetry -C linx_core/shared run pytest
poetry -C linx_core/services/identity_api install && poetry -C linx_core/services/identity_api run pytest
poetry -C linx_core/services/agent_bridge install && poetry -C linx_core/services/agent_bridge run pytest
poetry -C middleware/services/client_agent install && poetry -C middleware/services/client_agent run pytest
poetry -C middleware/services/routing install && poetry -C middleware/services/routing run pytest
poetry -C client install && poetry -C client run pytest
```
Expected: todos passam.

- [ ] **Step 2: Lint dos pacotes tocados**

```bash
poetry -C linx_core/services/agent_bridge run task lint
poetry -C middleware/services/client_agent run task lint
poetry -C middleware/services/routing run task lint
```
Expected: black/isort/flake8/mypy sem erro.

- [ ] **Step 3: Compose e docs**

```bash
docker compose -f linx_core/docker-compose.yml config >/dev/null && echo OK-core
docker compose -f deploy/docker-compose.yml config >/dev/null && echo OK-deploy
mkdocs build --strict
```
Expected: `OK-core`, `OK-deploy`, mkdocs sem erro.

- [ ] **Step 4: Varredura final de refs antigas**

Run: mesmo comando da Task 7 Step 5.
Expected: nenhuma linha ativa.

- [ ] **Step 5: Revisão do diff completo**

Run: `git status --short && git diff --stat`
Expected: apenas movimentos/edições esperados; nenhum artefato gerado rastreado (`.venv`, caches, `htmlcov`).
