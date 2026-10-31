# Reorganização de arquitetura: `linx_core/services` e `middleware/services`

- **Data:** 2026-10-08
- **Status:** Proposto
- **Escopo:** Reestruturação de pastas, correção de referências e limpeza de
  nomenclatura nos módulos Python do repositório.

## Contexto

O módulo antes chamado `saas_backend/` foi renomeado para `linx_core/` e seus
microserviços foram movidos para `linx_core/services/`. A intenção é deixar
explícito o que é microsserviço e o que é biblioteca, reduzindo a confusão do
nome antigo "saas backend".

A migração de arquivos foi iniciada manualmente, mas ficou **incompleta e
quebrada**: várias referências ainda apontam para os nomes e caminhos antigos.
Além disso, o diretório `middleware/` mistura o Client Agent (em
`middleware/src/agent`) e o serviço de `routing` (em `middleware/routing`) sem
uma estrutura comum.

Este documento define o estado-alvo e a lista de correções necessárias para
fechar a migração com build, execução, testes, CI e documentação consistentes.

### Problemas concretos encontrados

- `linx_core/services/*/pyproject.toml`: `linx-shared = { path = "../shared" }`
  resolve para `linx_core/services/shared` (inexistente); o correto é
  `../../shared`.
- `linx_core/docker-compose.yml`: `dockerfile: identity_api/Dockerfile` e
  `agent_bridge/Dockerfile` sem o prefixo `services/`.
- `linx_core/pyproject.toml` e `linx_core/scripts/run.sh`: usam
  `poetry -C identity_api` / `-C agent_bridge` (falta `services/`).
- `linx_core/alembic.ini`: `script_location = %(here)s/migrations`, mas as
  migrations foram movidas para `services/identity_api/migrations`.
- `.github/workflows/backend-ci.yml`: paths `saas_backend/**`,
  `working-directory: saas_backend` e matriz com `routing` (que não pertence
  mais ao core).
- `.github/workflows/client-agent-api-ci.yml`: paths e diretório
  `client_agent_api`, que não existe mais.
- `scripts/gen_proto.sh`: gera stubs em `saas_backend/...`,
  `client_agent_api/...` e `tenant_app_template/...`.
- `deploy/docker-compose.yml`: contextos `../saas_backend/.`,
  `../client_agent_api/.`, `../tenant_app_template/.` e `routing/Dockerfile`.
- `middleware/routing/pyproject.toml`: `linx-shared = { path = "../shared" }`
  quebrado.
- Documentação (`README.md`, `docs/`, `mkdocs.yml`, `PROGRESS.md`,
  `SPRINTS_BACKLOG.md`, PRD) cita os nomes antigos.
- Proto e stubs ainda usam o prefixo `saas_agent`.

## Objetivos

1. Tornar consistente a taxonomia: todo microsserviço mora em uma pasta
   `services/` do seu módulo.
2. Fazer build, execução local, testes e CI funcionarem com os novos caminhos.
3. Remover os resquícios de nomenclatura `saas` / `saas_backend` /
   `client_agent_api` / `tenant_app_template`.
4. Atualizar a documentação para refletir a nova estrutura.

## Não-objetivos

- **Refatorar o `routing`.** Ele será revisto em outro momento. Aqui ele apenas
  é movido para `middleware/services/routing` e tem o path dependency corrigido
  para continuar funcional. Nenhuma mudança de lógica interna.
- **Mexer em planos e specs históricos** sob `docs/superpowers/plans/` e
  `docs/superpowers/specs/` (exceto este documento). São registro do passado e
  não devem ser reescritos.
- Alterar o conteúdo de `infra/` (docker-compose base legado) e `frontend/`,
  exceto referências textuais de documentação.
- Refatorar a arquitetura do `routing` ou desacoplar sua dependência em
  `linx_shared`.

## Estado-alvo

```
linx_core/                      # antigo saas_backend — plano de controle SaaS
├── services/
│   ├── identity_api/           # REST :8000
│   │   ├── src/identity_api/
│   │   ├── tests/
│   │   ├── migrations/         # movidas de linx_core/migrations
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── agent_bridge/           # gRPC :50051
│       ├── src/agent_bridge/
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
├── shared/                     # biblioteca linx_shared
├── scripts/
├── alembic.ini
├── docker-compose.yml
└── pyproject.toml              # task-runner raiz (name=linx-core)

middleware/                     # antigo client_agent_api
├── services/
│   ├── client_agent/           # antigo middleware/{src/agent,tests,Dockerfile,pyproject}
│   │   ├── src/agent/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── routing/                # antigo middleware/routing
│       ├── src/routing/
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
└── pyproject.toml              # task-runner raiz (name=linx-middleware)

client/                         # antigo tenant_app_template (template por tenant)
frontend/  infra/  deploy/  proto/  scripts/  docs/  website/
```

O pacote Python importável do Client Agent continua sendo `agent` (imports como
`from agent.main import app` não mudam). Apenas a localização física muda.

## Mudanças

### 1. Mover `routing` e reorganizar `middleware/`

- `git mv middleware/routing middleware/services/routing`.
- `git mv middleware/pyproject.toml middleware/services/client_agent/pyproject.toml`.
- `git mv middleware/src middleware/services/client_agent/src`.
- `git mv middleware/tests middleware/services/client_agent/tests`.
- `git mv middleware/Dockerfile middleware/services/client_agent/Dockerfile`.
- Mover também os arquivos de apoio do Client Agent (`.flake8`, `.env`,
  `.env.example`, `README.md`, `.dockerignore`) para
  `middleware/services/client_agent/`.
- Criar `middleware/pyproject.toml` como task-runner raiz (espelhando
  `linx_core/pyproject.toml`): `package-mode = false`, `name = "linx-middleware"`,
  tasks de lint/test que rodam `poetry -C services/client_agent` e
  `poetry -C services/routing`.

### 2. Path dependencies

- `linx_core/services/identity_api/pyproject.toml`: `linx-shared = { path = "../../shared", develop = true }`.
- `linx_core/services/agent_bridge/pyproject.toml`: idem `../../shared`.
- `middleware/services/routing/pyproject.toml`: `linx-shared = { path = "../../../linx_core/shared", develop = true }`.
  (routing → `services/` → `middleware/` → raiz → `linx_core/shared`.)

### 3. Docker (Compose e Dockerfiles)

Contexto de build do core é a raiz de `linx_core/`; o Dockerfile espelha a
estrutura do repo dentro da imagem.

- `linx_core/docker-compose.yml`:
  - `identity_api`: `dockerfile: services/identity_api/Dockerfile`.
  - `agent_bridge`: `dockerfile: services/agent_bridge/Dockerfile`.
- `linx_core/services/identity_api/Dockerfile`:
  - `COPY shared ./shared`, `COPY services/identity_api ./services/identity_api`,
    `COPY services/identity_api/migrations ./services/identity_api/migrations`,
    `COPY alembic.ini ./alembic.ini`.
  - `poetry -C services/identity_api ...`.
  - `PYTHONPATH=/app/services/identity_api/src:/app/shared/src`.
  - entrypoint continua em `services/identity_api/docker-entrypoint.sh`.
- `linx_core/services/agent_bridge/Dockerfile`:
  - `COPY shared ./shared`, `COPY services/agent_bridge ./services/agent_bridge`.
  - `poetry -C services/agent_bridge ...`.
  - `PYTHONPATH=/app/services/agent_bridge/src:/app/shared/src`.
- `middleware/services/client_agent/Dockerfile`: contexto
  `middleware/services/client_agent/`; o Dockerfile atual já copia
  `pyproject.toml`, `poetry.lock` e `src` da raiz do contexto, então permanece
  inalterado salvo ajuste do caminho de contexto. Mantém `uvicorn agent.main:app`.
- `middleware/services/routing/Dockerfile`: contexto = **raiz do repositório**
  (routing depende de `linx_shared`);
  `COPY linx_core/shared ./shared`, `COPY middleware/services/routing ./routing`,
  `poetry -C routing ...`, `PYTHONPATH=/app/routing/src:/app/shared/src`.
- `deploy/docker-compose.yml`:
  - `identity_api`: `context: ../linx_core/.`, `dockerfile: services/identity_api/Dockerfile`.
  - `agent_bridge`: `context: ../linx_core/.`, `dockerfile: services/agent_bridge/Dockerfile`.
  - `client_agent`: `context: ../middleware/services/client_agent/`, `dockerfile: Dockerfile`.
  - `tenant_app`: `build: ../client/.`.
  - `routing`: `context: ../` (raiz), `dockerfile: middleware/services/routing/Dockerfile`.

### 4. Alembic

- `linx_core/alembic.ini`: `script_location = %(here)s/services/identity_api/migrations`.
- `linx_core/pyproject.toml` e `linx_core/scripts/run.sh`: invocar
  `poetry -C services/identity_api run alembic -c ../../alembic.ini <cmd>`.

### 5. Task-runners e scripts

- `linx_core/pyproject.toml`: `name = "linx-core"`, descrição atualizada,
  tasks `migrate`, `migration`, `test` apontando para `services/...`.
- `linx_core/scripts/run.sh`: `poetry -C services/identity_api ...` e
  `poetry -C services/agent_bridge ...`.
- `linx_core/scripts/deploy.sh`: revisar caminhos, se houver.

### 6. CI (GitHub Actions)

- `backend-ci.yml`:
  - `on.paths`: `linx_core/**`.
  - `working-directory: linx_core`.
  - Matriz: `[shared, services/identity_api, services/agent_bridge]` (remove
    `routing`, que passa a ser coberto pelo CI do middleware).
  - Instalação e execução via `poetry -C services/...`.
  - Migrations: `poetry -C services/identity_api run alembic -c ../../alembic.ini upgrade head`.
- `client-agent-api-ci.yml` → renomear para `middleware-ci.yml`:
  - `on.paths`: `middleware/**`.
  - `working-directory: middleware`.
  - Jobs cobrindo `services/client_agent` e `services/routing` via
    `poetry -C services/<svc>`.
- `mkdocs.yml` e `docs-ci.yml`: manter coerentes com os novos caminhos.

### 7. Renomear proto e stubs

- `git mv proto/saas_agent.proto proto/linx_agent.proto` (o `package` interno
  já é `linx`).
- Regenerar stubs (`scripts/gen_proto.sh`) → `linx_agent_pb2.py` /
  `linx_agent_pb2_grpc.py`.
- Atualizar imports e referências de `saas_agent_pb2` para `linx_agent_pb2`:
  - `linx_core/services/agent_bridge/src/agent_bridge/server.py`
  - `linx_core/services/agent_bridge/tests/test_grpc.py`
  - `client/src/tenant/grpc_client.py`, `client/tests/test_grpc_client.py`
  - `middleware/services/client_agent/src/agent/grpc_client.py`,
    `middleware/services/client_agent/tests/test_grpc_client.py`
  - Strings de `patch(...)` que citam `saas_agent_pb2_grpc`.
- `scripts/gen_proto.sh`: destinos e `sed` atualizados para
  `linx_core/shared/src/linx_shared/grpc`,
  `middleware/services/client_agent/src/agent/grpc`,
  `client/src/tenant/grpc`, e `linx_agent.proto`.

### 8. Documentação e nomenclatura

Atualizar referências textuais (nomes e caminhos):

- `README.md` (árvore e descrições dos módulos).
- `docs/index.md`, `docs/estrutura_de_pastas/estrutura.md`,
  `docs/comunicacao_entre_servicos.md`, `docs/PRD_PLATAFORMA_IOT.md`,
  `PRD_PLATAFORMA_IOT.md`.
- `docs/saas_backend/` → `docs/linx_core/` (via `git mv`), ajustando o README.
- `docs/middleware/README.md` (caminhos para `middleware/services/client_agent`).
- `docs/tenant_app_template/README.md` (nesse passo, apenas o que citar
  `tenant_app_template`/`saas_agent`).
- `middleware/services/client_agent/README.md` e `client/README.md`.
- `linx_core/README.md` (caminhos internos e nome "saas_backend").
- `mkdocs.yml` (nav): "SaaS Backend" → "Linx Core", caminhos de docs.
- `PROGRESS.md` e `SPRINTS_BACKLOG.md`: menções a `proto/saas_agent.proto`,
  `saas_backend`, `client_agent_api`, `tenant_app_template`.

## Estratégia de execução

1. Usar `git mv` em todas as movimentações para preservar histórico.
2. Ordem: (a) mover `routing` + reorganizar `middleware`; (b) corrigir path
   dependencies; (c) Docker/Compose; (d) task-runners/scripts/alembic;
   (e) CI; (f) proto/stubs; (g) documentação.
3. Cada etapa verificável de forma independente (ver abaixo).

## Verificação

- Path deps resolvem: `poetry -C linx_core/services/identity_api install`,
  `-C linx_core/services/agent_bridge install`,
  `-C middleware/services/routing install`,
  `-C middleware/services/client_agent install`.
- Testes: `taskipy test` de `linx_core` e de `middleware` passam; ou
  `poetry -C <pkg> run pytest` por pacote.
- Stubs: `bash scripts/gen_proto.sh` gera `linx_agent_pb2*` nos 3 destinos;
  `poetry -C <pkg> run python -c "from <pkg>.grpc import linx_agent_pb2"`
  funciona.
- Compose: `docker compose -f linx_core/docker-compose.yml config` e
  `docker compose -f deploy/docker-compose.yml config` sem erro.
- Docs: `mkdocs build --strict` sem links quebrados.
- CI: workflow files usam apenas caminhos existentes (checagem manual/grep).

## Riscos e mitigação

- **Geração dos stubs** requer `grpcio-tools` instalado por módulo. Se o
  ambiente não permitir, renomear arquivos e editar imports manualmente,
  garantindo que o conteúdo gerado siga consistente.
- **routing + linx_shared cross-módulo**: o Docker do routing precisa de
  contexto na raiz do repo. É uma dívida consciente; a refatoração do routing
  fica para outro trabalho.
- **CI de middleware**: unificar client_agent e routing em um único workflow
  novo (`middleware-ci.yml`) exige remover `client-agent-api-ci.yml`.

## Critérios de sucesso

- Nenhum arquivo ou referência ativa usa `saas_backend`, `client_agent_api` ou
  `tenant_app_template` (fora de documentos históricos em
  `docs/superpowers/plans` e `docs/superpowers/specs`).
- Todos os microsserviços estão sob um `services/` do seu módulo.
- Build, testes e CI passam com os novos caminhos.
- Documentação e `mkdocs` refletem a nova estrutura.
