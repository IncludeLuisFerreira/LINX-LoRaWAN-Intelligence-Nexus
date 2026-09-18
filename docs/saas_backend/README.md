# SaaS Backend

Backend do SaaS **LINX**, organizado como um conjunto de **microserviços de
plano de controle**. Cada serviço tem seu próprio pacote, `pyproject.toml`,
Dockerfile e processo — podendo ser implantado e escalado de forma
independente. O código comum fica na biblioteca compartilhada `linx_shared`.

## Estrutura

```
saas_backend/
├── shared/                    # biblioteca compartilhada (linx_shared)
│   ├── pyproject.toml
│   └── src/linx_shared/
│       ├── core/config.py     # Settings (DATABASE_URL, DB_CONNECT_TIMEOUT)
│       ├── db/                # engine, SessionLocal, get_db, Base
│       ├── models/            # tenant, application, user, tenant_user, device_routes
│       ├── schemas/           # schemas Pydantic da API
│       └── grpc/              # stubs do contrato AgentBridge
│
├── identity_api/              # microserviço REST (FastAPI)     → :8000
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   ├── src/identity_api/      # main.py + routes/ + templates/ + static/
│   └── tests/
│
├── agent_bridge/              # microserviço gRPC (AgentBridge)  → :50051
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── src/agent_bridge/      # server.py + config.py
│   └── tests/
│
├── migrations/                # Alembic (dono: identity_api)
├── alembic.ini
├── docker-compose.yml         # sobe db + identity_api + agent_bridge
├── scripts/deploy.sh
└── .env.example
```

> O código que antes ficava em `src/linx/` foi redistribuído: o que era comum
> virou `linx_shared`, o REST virou `identity_api` e o gRPC virou
> `agent_bridge`. Nenhum serviço importa código do outro.

## Serviços

### `identity_api` (REST — porta 8000)

Serviço FastAPI com os recursos de identidade/catálogo:

| Método  | Rota                       | Descrição                                          |
| :-----: | -------------------------- | -------------------------------------------------- |
|  `GET`  | `/`                        | Página inicial "Em Construção" (HTML).             |
|  `GET`  | `/health`                  | Health check do banco (`200`/`503`).               |
|  `GET`  | `/docs`                    | Swagger UI.                                        |
|  `GET`  | `/redoc`                   | ReDoc.                                             |
| `POST`  | `/api/v1/tenant/`          | Cria um tenant (`201` + `id` UUID v4).             |
|  `GET`  | `/api/v1/tenant/`          | Lista todos os tenants.                            |
|  `GET`  | `/api/v1/tenant/{id}`      | Busca um tenant pelo `id` (`404` se não existir).  |
| `PATCH` | `/api/v1/tenant/{id}`      | Atualiza parcialmente um tenant.                   |
| `DELETE`| `/api/v1/tenant/{id}`      | Remove um tenant (`204`).                          |
| `POST`  | `/api/v1/tenant/{id}/applications`          | Cria uma application no tenant.       |
|  `GET`  | `/api/v1/tenant/{id}/applications`          | Lista as applications do tenant.      |
|  `GET`  | `/api/v1/tenant/{id}/applications/{app_id}` | Busca uma application.                |
| `PATCH` | `/api/v1/tenant/{id}/applications/{app_id}` | Atualiza parcialmente uma application.|
| `DELETE`| `/api/v1/tenant/{id}/applications/{app_id}` | Remove uma application (`204`).       |

### `agent_bridge` (gRPC — porta 50051)

Servidor gRPC do contrato `AgentBridge`:

| RPC               | Direção            | Uso                                        |
| ----------------- | ------------------ | ------------------------------------------ |
| `GetAppConfig`    | Client Agent → SaaS | Config do tenant no startup.              |
| `ReportViolation` | Client Agent → SaaS | Notificação de violação (placeholder).    |

> O `agent_bridge` consulta o Postgres diretamente via `linx_shared`. Migrar
> para consultar o `identity_api` é uma evolução futura (desacoplamento total).

## Desenvolvimento local

Cada serviço é um projeto Poetry independente que depende de `linx_shared` por
caminho (`../shared`). A raiz do `saas_backend/` é um projeto Poetry
(`package-mode = false`) só com os atalhos `task`.

```bash
# Instalar dependências (uma vez por serviço + task runner da raiz)
poetry install                       # task runner (taskipy)
poetry -C shared install
poetry -C identity_api install
poetry -C agent_bridge install
```

Subir os dois serviços de uma vez (carrega o `.env` da raiz e sobe REST + gRPC;
`Ctrl+C` encerra ambos):

```bash
poetry run task run
```

Ou individualmente:

```bash
poetry -C identity_api run uvicorn identity_api.main:app --reload
poetry -C agent_bridge run python -m agent_bridge.server
```

> `poetry -C <serviço>` executa o comando com o diretório de trabalho do
> serviço; por isso o `task run` carrega o `.env` da raiz antes de subir os
> processos.

### Atalhos (`task`)

| Task         | Ação                                                          |
| ------------ | ------------------------------------------------------------- |
| `run`        | Sobe `identity_api` + `agent_bridge` em modo dev.             |
| `run-docker` | `docker compose up --build` (foreground).                     |
| `up`         | `docker compose up -d --build`.                               |
| `down`       | `docker compose down`.                                        |
| `migrate`    | Aplica as migrations do Alembic (`upgrade head`).             |
| `migration`  | Gera nova migration (`revision --autogenerate -m "<msg>"`).   |
| `test`       | Roda os testes dos três pacotes.                              |

### Testes

```bash
poetry run task test

# ou por serviço
poetry -C shared run pytest
poetry -C identity_api run pytest   # exige Postgres em localhost:5432
poetry -C agent_bridge run pytest   # exige Postgres em localhost:5432
```

## Banco de dados e migrações

O schema é versionado com **Alembic** (em `migrations/`). O dono das tabelas é
o `identity_api`, então é ele que roda as migrações no startup.

| Comando                                              | Descrição                                  |
| ---------------------------------------------------- | ------------------------------------------ |
| `poetry run task migrate`                            | Aplica todas as migrações pendentes.       |
| `poetry -C identity_api run alembic -c ../alembic.ini downgrade -1` | Reverte a última migração.    |
| `poetry run task migration "<msg>"`                  | Gera nova migração a partir dos models.    |

> O `alembic.ini` fica na raiz do `saas_backend/`; como `poetry -C identity_api`
> muda o diretório de trabalho para `identity_api/`, é preciso apontar o config
> com `-c ../alembic.ini` (os atalhos `task migrate`/`task migration` já fazem
> isso).

> Os models ficam em `linx_shared.models`; o `migrations/env.py` importa de lá.

## Contrato gRPC

O contrato `AgentBridge` é definido em `proto/saas_agent.proto` e versionado na
raiz do repositório. Os stubs Python são gerados em
`shared/src/linx_shared/grpc/` (e em `client_agent_api/src/agent/grpc/`).

```bash
bash scripts/gen_proto.sh
```

## Docker / Deploy

O `docker-compose.yml` sobe três serviços: `db` (Postgres), `identity_api` e
`agent_bridge`.

```bash
cd saas_backend
cp .env.example .env   # ajuste POSTGRES_PASSWORD
docker compose up -d --build
curl -i http://localhost:8000/health
```

Resposta esperada (`200`):

```json
{"status":"ok","db":true}
```

### Variáveis de ambiente

| Variável             | Descrição                                                        | Default no exemplo              |
| -------------------- | ---------------------------------------------------------------- | ------------------------------- |
| `POSTGRES_USER`      | Usuário do Postgres.                                             | `linx`                          |
| `POSTGRES_PASSWORD`  | Senha do Postgres (troque em produção).                          | `change-me-in-production`       |
| `POSTGRES_DB`        | Banco do Postgres.                                               | `linx`                          |
| `DATABASE_URL`       | URL SQLAlchemy (o Compose sobrescreve o host para `db`).         | `postgresql+psycopg://linx:...@localhost:5432/linx` |
| `DB_CONNECT_TIMEOUT` | Timeout de conexão com o banco (segundos).                       | `5`                             |
| `GRPC_HOST`          | Endereço de bind do `agent_bridge`.                              | `0.0.0.0`                       |
| `GRPC_PORT`          | Porta do `agent_bridge`.                                         | `50051`                         |

> **Atenção (P0):** o gRPC ainda não tem autenticação e `GetAppConfig` devolve
> usuário/senha do Postgres. Restrinja a porta `50051` no Security Group ao IP
> do Client Agent até o mTLS (Sprint 5). Nunca exponha a `0.0.0.0/0`.

### Runbook — EC2 `t3.small`

1. **Security Group (inbound):** `22` (SSH, restrito), `8000` (REST),
   `50051` (gRPC, **somente** o IP do Client Agent).
2. Instale Docker e o plugin Compose, clone o repositório.
3. `cd saas_backend && cp .env.example .env` e defina uma senha forte.
4. `./scripts/deploy.sh`.
5. Verifique de fora: `curl -i http://<ec2-ip>:8000/health`.
