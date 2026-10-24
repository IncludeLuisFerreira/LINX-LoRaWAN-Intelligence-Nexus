# Linx Core

Backend do SaaS **LINX**, organizado como um conjunto de **microserviços de
plano de controle**. Cada serviço tem seu próprio pacote, `pyproject.toml`,
Dockerfile e processo — podendo ser implantado e escalado de forma
independente. O código comum fica na biblioteca compartilhada `linx_shared`.

## Estrutura

```
linx_core/
├── services/
│   ├── identity_api/          # microserviço REST (FastAPI)     → :8000
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── docker-entrypoint.sh
│   │   ├── migrations/        # Alembic (dono: identity_api)
│   │   ├── src/identity_api/  # main.py + routes/ + templates/ + static/
│   │   └── tests/
│   ├── agent_bridge/          # microserviço gRPC (AgentBridge)  → :50051
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/agent_bridge/  # server.py + config.py
│   │   └── tests/
│   └── docker_provisioner/    # microserviço gRPC (DockerProvisioner) → :50052
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── src/docker_provisioner/  # server.py + docker_service.py
│       └── tests/
│
├── shared/                    # biblioteca compartilhada (linx_shared)
│   ├── pyproject.toml
│   └── src/linx_shared/
│       ├── core/config.py     # Settings (DATABASE_URL, DB_CONNECT_TIMEOUT)
│       ├── db/                # engine, SessionLocal, get_db, Base
│       ├── models/            # tenant, application, user, tenant_user, device_routes, devices
│       ├── schemas/           # schemas Pydantic da API
│       └── grpc/              # stubs dos contratos AgentBridge/DockerProvisioner
│
├── alembic.ini
├── docker-compose.yml         # sobe db + identity_api + agent_bridge + docker_provisioner
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
| `POST`  | `/api/v1/tenant/{id}/applications/{app_id}/provision` | Provisiona o container Docker da application via gRPC. |
| `POST`  | `/api/v1/devices`                          | Cria um device (`201`) e provisiona no ChirpStack. |
|  `GET`  | `/api/v1/devices?app_id={id}`              | Lista os devices de uma application.               |
| `DELETE`| `/api/v1/devices/{id}`                     | Remove um device (`204`) e deleta no ChirpStack.   |

### `agent_bridge` (gRPC — porta 50051)

Servidor gRPC do contrato `AgentBridge`:

| RPC               | Direção            | Uso                                        |
| ----------------- | ------------------ | ------------------------------------------ |
| `GetAppConfig`    | Client Agent → SaaS | Config do tenant no startup.              |
| `ReportViolation` | Client Agent → SaaS | Notificação de violação (placeholder).    |

> O `agent_bridge` consulta o Postgres diretamente via `linx_shared`. Migrar
> para consultar o `identity_api` é uma evolução futura (desacoplamento total).

### `docker_provisioner` (gRPC — porta 50052)

Serviço interno que cria e reaproveita containers Docker por aplicação. É o
único serviço do plano de controle com acesso ao `/var/run/docker.sock`.

| RPC | Direção | Uso |
| --- | ------- | --- |
| `ProvisionApplication` | identity_api → docker_provisioner | Cria/reaproveita o container da aplicação e devolve porta/rede. |

Contrato em `proto/linx_docker_provisioner.proto`. A chamada exige o metadado
`authorization: Bearer <SERVICE_TOKEN>` e a porta não é publicada no host.

## Provisionamento Docker (issue #58)

Fluxo do endpoint:

1. `identity_api` valida o `tenant_id` e a `application_id` no Postgres.
2. Chama o `docker_provisioner` por gRPC com apenas o `app_id`.
3. O provisioner:
   - reutiliza o container se já existir label `linx.application.id`;
   - cria/reutiliza a rede `linx-app-<app_id>`;
   - sorteia uma porta no range `8100–9100` (`secrets.SystemRandom`), consulta
     portas publicadas no Docker e re-tenta se o daemon rejeitar uma porta já
     alocada;
   - sobe a imagem `PROVISION_IMAGE` em `0.0.0.0:<porta>`;
   - injeta `APP_ID`, `DB_PASSWORD`, `MQTT_TOPIC` e `SERVICE_TOKEN`.
4. A resposta HTTP devolve `container_id`, `port`, `network`, `image`,
   `status`, `created` e `mqtt_topic`. `DB_PASSWORD` nunca é retornado.

Request de exemplo:

```bash
TOKEN="$(grep '^SERVICE_TOKEN=' .env | cut -d= -f2-)"
curl -X POST \
  "http://localhost:8000/api/v1/tenant/$TENANT_ID/applications/$APP_ID/provision" \
  -H "X-Service-Token: $TOKEN"
```

Resposta (`201` na criação, `200` quando o container já existia):

```json
{
  "container_id": "3f1c...",
  "port": 8421,
  "network": "linx-app-<app_id>",
  "image": "linx-tenant-app:latest",
  "status": "running",
  "created": true,
  "mqtt_topic": "application/<app_id>/device/+/event/up"
}
```

Códigos de erro: `401` sem token, `404` tenant/app inexistente, `409` estado
inconsistente no provisioner, `502` falha do Docker/provisioner, `503`
indisponível ou sem porta livre e `504` timeout gRPC.

### Segurança do socket Docker

O `docker_provisioner` monta `/var/run/docker.sock`, o que dá poder equivalente
a root no host. Use apenas em ambiente controlado. O `DOCKER_GID` deve ser o
GID do grupo dono do socket:

```bash
stat -c '%g' /var/run/docker.sock
```

Preencha `DOCKER_GID` no `.env` do `linx_core/`. O `identity_api` **não** monta
o socket.

## Desenvolvimento local

Cada serviço é um projeto Poetry independente que depende de `linx_shared` por
caminho (`../../shared`). A raiz do `linx_core/` é um projeto Poetry
(`package-mode = false`) só com os atalhos `task`.

```bash
# Instalar dependências (uma vez por serviço + task runner da raiz)
poetry install                       # task runner (taskipy)
poetry -C shared install
poetry -C services/identity_api install
poetry -C services/agent_bridge install
poetry -C services/docker_provisioner install
```

Subir os três serviços de uma vez (carrega o `.env` da raiz e sobe REST + os
dois servidores gRPC; `Ctrl+C` encerra todos):

```bash
poetry run task run
```

Ou individualmente:

```bash
poetry -C services/identity_api run uvicorn identity_api.main:app --reload
poetry -C services/agent_bridge run python -m agent_bridge.server
poetry -C services/docker_provisioner run python -m docker_provisioner.server
```

> `poetry -C <serviço>` executa o comando com o diretório de trabalho do
> serviço; por isso o `task run` carrega o `.env` da raiz antes de subir os
> processos.

### Atalhos (`task`)

| Task         | Ação                                                          |
| ------------ | ------------------------------------------------------------- |
| `run`        | Sobe `identity_api` + `agent_bridge` + `docker_provisioner`.  |
| `run-docker` | `docker compose up --build` (foreground).                     |
| `up`         | `docker compose up -d --build`.                               |
| `down`       | `docker compose down`.                                        |
| `migrate`    | Aplica as migrations do Alembic (`upgrade head`).             |
| `migration`  | Gera nova migration (`revision --autogenerate -m "<msg>"`).   |
| `test`       | Roda os testes dos quatro pacotes.                            |

### Testes

```bash
poetry run task test

# ou por serviço
poetry -C shared run pytest
poetry -C services/identity_api run pytest   # exige Postgres em localhost:5432
poetry -C services/agent_bridge run pytest   # exige Postgres em localhost:5432
poetry -C services/docker_provisioner run pytest  # não exige Docker real
```

## Banco de dados e migrações

O schema é versionado com **Alembic** (em `services/identity_api/migrations/`).
O dono das tabelas é o `identity_api`, então é ele que roda as migrações no
startup.

| Comando                                              | Descrição                                  |
| ---------------------------------------------------- | ------------------------------------------ |
| `poetry run task migrate`                            | Aplica todas as migrações pendentes.       |
| `poetry -C services/identity_api run alembic -c ../../alembic.ini downgrade -1` | Reverte a última migração.    |
| `poetry run task migration "<msg>"`                  | Gera nova migração a partir dos models.    |

> O `alembic.ini` fica na raiz do `linx_core/`; como
> `poetry -C services/identity_api` muda o diretório de trabalho para
> `services/identity_api/`, é preciso apontar o config com `-c ../../alembic.ini`
> (os atalhos `task migrate`/`task migration` já fazem isso).

> Os models ficam em `linx_shared.models`; o `migrations/env.py` importa de lá.

## Contratos gRPC

Os contratos ficam em `proto/`:
- `linx_agent.proto` — `AgentBridge` (`:50051`);
- `linx_docker_provisioner.proto` — `DockerProvisioner` (`:50052`).

Os stubs Python são gerados em um único lugar:
`shared/src/linx_shared/grpc/` (pacote `linx_shared`). `identity_api`,
`agent_bridge`, `docker_provisioner` e `client_agent` consomem esse pacote via
path dependency, sem cópia local (#215).

```bash
bash scripts/gen_proto.sh
```

## Docker / Deploy

O `docker-compose.yml` sobe quatro serviços: `db` (Postgres), `identity_api`,
`agent_bridge` e `docker_provisioner`.

```bash
# a partir da raiz: builda a imagem mínima usada no provisionamento
make build-tenant-image

cd linx_core
cp .env.example .env   # ajuste POSTGRES_PASSWORD, SERVICE_TOKEN e DOCKER_GID
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
| `CHIRPSTACK_HOST`    | Endereço gRPC do ChirpStack.                                     | `localhost:8080`                |
| `CHIRPSTACK_API_TOKEN` | Token Bearer de acesso à API do ChirpStack.                    | *(obrigatório)*                 |
| `CHIRPSTACK_DEVICE_PROFILE_ID` | UUID do Device Profile usado ao provisionar devices.  | *(vazio)*                       |
| `SERVICE_TOKEN`      | Token do plano de controle e da chamada gRPC (mín. 32 chars).    | *(obrigatório)*                 |
| `DOCKER_GID`         | GID do grupo dono de `/var/run/docker.sock`.                     | `990`                           |
| `PROVISIONER_GRPC_HOST` | Endereço gRPC do provisioner visto pelo `identity_api`.        | `localhost:50052` (Compose: `docker_provisioner:50052`) |
| `PROVISIONER_GRPC_TIMEOUT_SECONDS` | Timeout da chamada gRPC.                             | `10`                            |
| `PROVISION_IMAGE`    | Imagem Docker provisionada por aplicação.                        | `linx-tenant-app:latest`        |
| `PROVISION_PORT_MIN` | Início do range de portas publicado no host.                     | `8100`                          |
| `PROVISION_PORT_MAX` | Fim do range de portas publicado no host.                        | `9100`                          |
| `PROVISION_BIND_HOST` | Interface de bind da porta publicada.                          | `0.0.0.0`                       |
| `PROVISION_NETWORK_PREFIX` | Prefixo da rede Docker por aplicação.                      | `linx-app`                      |
| `PROVISION_CONTAINER_PORT` | Porta interna do container do tenant.                      | `8000`                          |

> **Atenção (P0):** o gRPC ainda não tem autenticação e `GetAppConfig` devolve
> usuário/senha do Postgres. Restrinja a porta `50051` no Security Group ao IP
> do Client Agent até o mTLS (Sprint 5). Nunca exponha a `0.0.0.0/0`.

### Runbook — EC2 `t3.small`

1. **Security Group (inbound):** `22` (SSH, restrito), `8000` (REST),
   `50051` (gRPC, **somente** o IP do Client Agent).
2. Instale Docker e o plugin Compose, clone o repositório.
3. `cd linx_core && cp .env.example .env` e defina uma senha forte.
4. `./scripts/deploy.sh`.
5. Verifique de fora: `curl -i http://<ec2-ip>:8000/health`.
