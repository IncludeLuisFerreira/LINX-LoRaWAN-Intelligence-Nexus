# SaaS Backend

Backend do SaaS desenvolvido em Python utilizando **FastAPI**, com gerenciamento de dependências através do **Poetry** e ferramentas de qualidade e testes.

## 📋 O que foi feito

* [x] Instalação do Poetry.
* [x] Instalação das dependências Python.
* [x] Configuração das ferramentas de qualidade de código.
* [x] Configuração do ambiente de testes.
* [x] Configuração de coverage de testes.
* [x] Configuração do Isort.
* [x] Início da API FastAPI (`linx.main:app`).
* [x] Endpoint de health check (`/health`).
* [x] Página inicial servida via Jinja2 + arquivos estáticos (`/`).
* [x] Configuração do SQLAlchemy 2.0 + Psycopg (PostgreSQL).
* [x] Models SQLAlchemy 2.0: `tenant`, `application`, `user`, `tenant_user`.
* [x] Configuração centralizada via `pydantic-settings` (`core/config.py`).
* [x] Alembic configurado com migration inicial das 4 tabelas.
* [x] CRUD REST de Tenants em `/api/v1/tenant` (primeiro endpoint público do SaaS).

## 📍 Endpoints disponíveis

| Método  | Rota                       | Descrição                                                  |
| :-----: | -------------------------- | ---------------------------------------------------------- |
|  `GET`  | `/`                        | Página inicial "Em Construção" (HTML).                     |
|  `GET`  | `/health`                  | Health check retornando `{"status": "ok"}`.                |
|  `GET`  | `/docs`                    | Documentação interativa (Swagger UI).                      |
|  `GET`  | `/redoc`                   | Documentação alternativa (ReDoc).                          |
| `POST`  | `/api/v1/tenant/`          | Cria um tenant (`201` + `id` UUID v4).                     |
|  `GET`  | `/api/v1/tenant/`          | Lista todos os tenants (`200` + array).                    |
|  `GET`  | `/api/v1/tenant/{id}`      | Busca um tenant pelo `id` (`404` se não existir).          |
| `PATCH` | `/api/v1/tenant/{id}`      | Atualiza parcialmente um tenant (`404` se não existir).    |
| `DELETE`| `/api/v1/tenant/{id}`      | Remove um tenant (`204`; `404` se não existir).            |
| `POST`  | `/api/v1/tenant/{id}/applications`            | Cria uma application no tenant (`201`; `404` se o tenant não existir). |
|  `GET`  | `/api/v1/tenant/{id}/applications`            | Lista as applications do tenant (`200` + array; `404` se o tenant não existir). |
|  `GET`  | `/api/v1/tenant/{id}/applications/{app_id}`   | Busca uma application pelo `app_id` (`404` se não existir). |
| `PATCH` | `/api/v1/tenant/{id}/applications/{app_id}`   | Atualiza parcialmente uma application (`404` se não existir). |
| `DELETE`| `/api/v1/tenant/{id}/applications/{app_id}`   | Remove uma application (`204`; `404` se não existir). |

> O `{id}` e o `{app_id}` são `UUID` (v4) gerados automaticamente pelo banco na criação.

## 🔄 CRUD de Tenants

O primeiro endpoint REST público do SaaS permite gerenciar as organizações (tenants).
Os schemas ficam em `src/linx/schemas/tenant.py` e as rotas em `src/linx/routes/tenant.py`
(prefixo `/api/v1/tenant`, registrado em `linx/main.py`).

### Criação

`name` é obrigatório (até 50 caracteres); `description` é opcional (até 100 caracteres, default `""`):

```bash
curl -X POST localhost:8000/api/v1/tenant/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "ACME"}'
```

Resposta (`201`) — como `description` não foi enviado, vem `""`. O header `Location` aponta para o recurso criado (`/api/v1/tenant/{id}`):

```json
{
  "name": "ACME",
  "description": "",
  "id": "89f9a8f6-...-uuid-v4",
  "created_at": "2026-09-07T22:00:00Z",
  "updated_at": "2026-09-07T22:00:00Z"
}
```

### Consulta, atualização e remoção

```bash
# Listar todos os tenants (200) — retorna um array
curl localhost:8000/api/v1/tenant/

# Buscar por id (200) — 404 se o tenant não existir
curl localhost:8000/api/v1/tenant/<UUID>

# Atualização parcial (200) — apenas os campos enviados são alterados;
# 'updated_at' é atualizado automaticamente pelo model
curl -X PATCH localhost:8000/api/v1/tenant/<UUID> \
  -H 'Content-Type: application/json' \
  -d '{"name": "ACME Ltda"}'

# Remover (204, sem corpo) — hard-delete; os filhos do tenant
# (applications/tenant_user) são removidos em cascata via FK ondelete=CASCADE
curl -X DELETE localhost:8000/api/v1/tenant/<UUID> -i
```

O Swagger em `/docs` lista os 5 endpoints da API de tenants.

## 🔄 CRUD de Applications

O segundo recurso REST público do SaaS permite gerenciar as aplicações
vinculadas a um tenant (organização). Os schemas ficam em
`src/linx/schemas/application.py` e as rotas em `src/linx/routes/application.py`
(prefixo `/api/v1/tenant`, registrado em `linx/main.py`).

Toda rota exige um `{tenant_id}` existente (caso contrário, `404`).

### Criação

`name` é obrigatório (até 50 caracteres); `description` é opcional (até 100 caracteres, default `""`):

```bash
curl -X POST localhost:8000/api/v1/tenant/<UUID>/applications \
  -H 'Content-Type: application/json' \
  -d '{"name": "Fazenda"}'
```

Resposta (`201`) — o header `Location` aponta para o recurso criado
(`/api/v1/tenant/{id}/applications/{app_id}`):

```json
{
  "name": "Fazenda",
  "description": "",
  "id": "89f9a8f6-...-uuid-v4",
  "created_at": "2026-09-07T22:00:00Z",
  "updated_at": "2026-09-07T22:00:00Z"
}
```

### Consulta, atualização e remoção

```bash
# Listar as applications de um tenant (200) — 404 se o tenant não existir
curl localhost:8000/api/v1/tenant/<UUID>/applications

# Buscar por app_id (200) — 404 se a application não existir
curl localhost:8000/api/v1/tenant/<UUID>/applications/<APP_UUID>

# Atualização parcial (200) — apenas os campos enviados são alterados;
# 'updated_at' é atualizado automaticamente pelo model
curl -X PATCH localhost:8000/api/v1/tenant/<UUID>/applications/<APP_UUID> \
  -H 'Content-Type: application/json' \
  -d '{"name": "Fazenda Norte"}'

# Remover (204, sem corpo)
curl -X DELETE localhost:8000/api/v1/tenant/<UUID>/applications/<APP_UUID> -i
```

O Swagger em `/docs` lista os 5 endpoints da API de applications.

## ⚙️ Instalação

Instale as dependências do projeto:

```bash
poetry install
```

## ▶️ Executando o projeto

Para iniciar o servidor FastAPI utilizando o Uvicorn:

```bash
poetry run uvicorn linx.main:app --reload
```

O parâmetro `--reload` habilita o recarregamento automático do servidor durante o desenvolvimento.

## 🗄️ Banco de Dados

O projeto utiliza **SQLAlchemy 2.0** (estilo declarativo com `Mapped`/`mapped_column`) e **Psycopg 3** para o PostgreSQL.

### Estrutura

| Arquivo                          | Responsabilidade                                                    |
| -------------------------------- | ------------------------------------------------------------------- |
| `src/linx/db/base_class.py`      | Declara `Base = declarative_base()`.                                |
| `src/linx/db/base.py`            | Engine, `SessionLocal` e registro dos models em `Base.metadata`.    |
| `src/linx/models/`               | Definição dos models (`tenant`, `application`, `user`, `tenant_user`). |
| `src/linx/schemas/`              | Schemas Pydantic da API (`tenant.py` → Create/Update/Response).     |
| `src/linx/routes/`               | Rotas/endpoints da API (`tenant.py` → CRUD em `/api/v1/tenant`).    |

A `DATABASE_URL` está configurada em `src/linx/db/base.py` (padrão: `postgresql+psycopg://linx:linx@localhost:5432/linx`).

### Models

Os nomes de entidade seguem o schema do **ChirpStack v4** para facilitar a integração.

| Model         | Tabela        | Descrição                                                                     |
| ------------- | ------------- | ----------------------------------------------------------------------------- |
| `Tenant`      | `tenant`      | Organização (tenant), com limites de gateways/dispositivos e `tags` (JSONB).  |
| `Application` | `application` | Aplicação pertencente a um tenant (`tenant_id` FK → `tenant.id`).             |
| `User`        | `user`        | Usuário global (`email` único, `password_hash`, flags de admin/ativo).        |
| `TenantUser`  | `tenant_user` | Vínculo/papel de um usuário em um tenant (PK composta + flags de RBAC).       |

- Todos os `id` usam `UUID` (v4) como chave primária (RF-040).
- `TenantUser` usa PK composta (`tenant_id`, `user_id`), fiel ao ChirpStack.
- Relacionamentos ORM: `Tenant.applications` ↔ `Application.tenant` e `Tenant.tenant_users` ↔ `TenantUser` ↔ `User.tenant_users`.
- `created_at`/`updated_at` são gerados **no ORM** (`default`/`onupdate` como callables Python com `datetime.now(timezone.utc)`), avaliados por linha no INSERT/UPDATE. Decisão: mantém-se no lado Python para um único app instance e evita trigger no Postgres (que não tem cláusula `ON UPDATE`); migrar para `server_default` pode ser revisitado se houver múltiplas instâncias ou updates diretos no banco.

### Verificando os models

```bash
poetry run python -c "from linx.db.base import Base; print(Base.metadata.tables.keys())"
```

Saída esperada:

```text
dict_keys(['application', 'tenant', 'tenant_user', 'user'])
```

### Migrações (Alembic)

O schema é versionado com **Alembic**. A URL do banco é resolvida por `Settings` (`DATABASE_URL` ou default local).

| Comando                                  | Descrição                                  |
| ---------------------------------------- | ------------------------------------------ |
| `poetry run alembic upgrade head`        | Aplica todas as migrações pendentes.       |
| `poetry run alembic downgrade -1`        | Reverte a última migração.                 |
| `poetry run alembic current`             | Mostra a revisão aplicada.                 |
| `poetry run alembic revision --autogenerate -m "<msg>"` | Gera nova migração a partir dos models. |

Para aplicar localmente (exige o Postgres de `infra/docker-compose.base.yml`):

```bash
docker compose -f infra/docker-compose.base.yml up -d postgres
poetry run alembic upgrade head
```

## 🧪 Testes

Para executar os testes:

```bash
task test
```

Também é possível executar o Pytest diretamente:

```bash
pytest
```

### Testando endpoints

Para testar um endpoint diretamente pelo terminal:

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{
  "status": "ok"
}
```

## 📦 Dependências do projeto

### FastAPI

Framework web moderno e de alto desempenho para a construção de APIs em Python, com validação automática de dados via Pydantic e documentação interativa (Swagger/ReDoc).

### Uvicorn

Servidor web ASGI de alta performance baseado em `uvloop` e `httptools`, utilizado para executar a aplicação FastAPI.

### Pydantic Settings

Extensão do Pydantic para gerenciamento de configurações e variáveis de ambiente da aplicação através de classes tipadas e validação estática.

### Jinja2

Motor de templates para Python, utilizado na renderização de páginas HTML dinâmicas no lado do servidor.

### SQLAlchemy

ORM (*Object-Relational Mapping*) e SQL Toolkit para abstração, consulta e manipulação de banco de dados relacional em Python.

### Psycopg

Adaptador de banco de dados PostgreSQL de terceira geração para Python, focado em alta performance, concorrência e recursos assíncronos.

## 🛠️ Dependências de desenvolvimento

### Pytest

Framework para testes automatizados em Python. Permite escrever e executar testes unitários e de integração de forma simples e escalável.

### Black

Formatador automático de código Python (*uncompromising code formatter*). Aplica regras consistentes de formatação ao código.

### Isort

Utilitário para ordenação e organização automática das declarações de `import` em ordem alfabética e por seções de dependência.

### Flake8

Linter para Python que realiza análise estática do código, identificando problemas como erros de sintaxe, variáveis não utilizadas e violações das convenções da PEP 8.

### Mypy

Verificador estático de tipos para Python. Analisa as anotações de tipo (*type hints*) para identificar possíveis erros de compatibilidade e problemas de lógica antes da execução do código.

### Pytest-cov

Plugin do Pytest integrado ao `coverage.py` para medir a cobertura de código pelos testes e gerar relatórios em terminal e HTML.

### httpx2

Client HTTP assíncrono utilizado pelo `TestClient` do FastAPI/Starlette para execução dos testes de endpoints da API.

### Taskipy

Task runner para Python que permite criar atalhos padronizados para comandos utilizados frequentemente no projeto, como execução de linters, testes e servidor.
