# Deploy SaaS Backend on EC2 (Docker Compose) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empacotar o `saas_backend` em Docker e orquestrar `app + PostgreSQL` via `docker-compose.prod.yml`, expondo REST na porta `8000` e gRPC na `50051`, com `restart: unless-stopped` e `GET /health` retornando `200`, pronto para deploy em EC2 `t3.small`.

**Architecture:** Imagem Docker multi-stage (builder instala dependências com Poetry; runtime leve, usuário não-root). O `docker-entrypoint.sh` aplica as migrations do Alembic (com retry) e sobe o Uvicorn, que no lifespan também sobe o servidor gRPC. O Compose sobe dois serviços na mesma rede: `db` (Postgres 15, volume nomeado, healthcheck `pg_isready`) e `app` (build local, portas 8000/50051, `depends_on: db healthy`). Nada é publicado na AWS agora; o deploy real é um runbook documentado no README.

**Tech Stack:** Docker 28, Docker Compose v2, Python 3.12, Poetry 2.4.1, FastAPI, Uvicorn, SQLAlchemy 2.0 + psycopg 3, Alembic, grpcio, PostgreSQL 15.

**Base branch:** `develop` (já contém o merge do PR #157 — `/health` com DB + gRPC).

**Branch de trabalho:** `issue30_deploy_saas_backend` (já criada e ativa).

---

## File Structure

| Arquivo | Ação | Responsabilidade |
| --- | --- | --- |
| `saas_backend/.dockerignore` | Preencher (existe vazio) | Evitar copiar `.env`, caches e venv para o build context. |
| `saas_backend/Dockerfile` | Reescrever (existe, cópia errada) | Build multi-stage; runtime com `PYTHONPATH=/app/src`, `EXPOSE 8000 50051`, entrypoint. |
| `saas_backend/docker-entrypoint.sh` | Criar | Rodar `alembic upgrade head` (com retry) e `exec uvicorn`. |
| `saas_backend/.env.example` | Criar | Template versionado das variáveis de ambiente. |
| `saas_backend/docker-compose.prod.yml` | Criar | Serviços `db` + `app`, healthchecks, portas, `restart: unless-stopped`. |
| `saas_backend/scripts/deploy.sh` | Criar | `git pull` + `docker compose up -d --build` na EC2. |
| `saas_backend/README.md` | Modificar | Seção de env vars + runbook de deploy AWS + verificação. |

**Fora de escopo (issue separada):** Nginx/TLS. **Fora de escopo (execução futura pelo usuário):** provisionar a EC2/Security Group de fato.

---

## Task 0: Confirmar o estado do branch

**Files:** nenhum.

- [ ] **Step 1: Confirmar branch e árvore**

Run:
```bash
git -C /home/includeluisferreira/Documentos/projetos/reais/Lynx branch --show-current
git -C /home/includeluisferreira/Documentos/projetos/reais/Lynx status --short
```
Expected: `issue30_deploy_saas_backend` e apenas arquivos não rastreados esperados (`saas_backend/Dockerfile`, `saas_backend/.dockerignore`, `docs/superpowers/`).

- [ ] **Step 2: Confirmar que a base está atualizada com a develop**

Run:
```bash
git -C /home/includeluisferreira/Documentos/projetos/reais/Lynx log --oneline -1 develop
git -C /home/includeluisferreira/Documentos/projetos/reais/Lynx log --oneline -1
```
Expected: ambos apontam para o merge do PR #157 (`ba05749 Merge pull request #157 ...`) ou o HEAD já contém a develop.

---

## Task 1: `.dockerignore`

**Files:**
- Modify: `saas_backend/.dockerignore` (hoje vazio)

- [ ] **Step 1: Escrever o conteúdo**

Conteúdo de `saas_backend/.dockerignore`:

```gitignore
**/.env
**/__pycache__
**/*.pyc
**/.pytest_cache
**/htmlcov
**/.mypy_cache
**/.venv
**/.coverage
```

- [ ] **Step 2: Verificar que o `.env` não entra no build context**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend && touch .env && docker build --no-cache -t linx-saas-backend:check . 2>&1 | tail -5
```
Expected: o build **falha** neste ponto (o Dockerfile ainda é o antigo, sem entrypoint) — isso é esperado; o objetivo do Step é só confirmar que o build context é aceito. Se quiser, pule este step e faça o build real no Task 2, Step 3.

- [ ] **Step 3: Remover o `.env` de teste**

Run:
```bash
rm -f /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend/.env
```

- [ ] **Step 4: Commit**

```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git add saas_backend/.dockerignore
git commit -m "chore(deploy): adiciona .dockerignore do saas_backend"
```

---

## Task 2: `Dockerfile` + `docker-entrypoint.sh`

**Files:**
- Modify: `saas_backend/Dockerfile`
- Create: `saas_backend/docker-entrypoint.sh`

**Por que reescrever o Dockerfile:** o arquivo atual é uma cópia do `client_agent_api` e aponta para `agent.main:app` (módulo inexistente no `saas_backend`), não copia `alembic.ini`/`migrations`, não expõe a porta gRPC e não roda migrations.

- [ ] **Step 1: Criar o `docker-entrypoint.sh`**

Conteúdo de `saas_backend/docker-entrypoint.sh`:

```sh
#!/bin/sh
set -e

echo "Applying database migrations..."
until alembic upgrade head; do
  echo "Migration failed (database not ready?). Retrying in 3s..."
  sleep 3
done

echo "Starting uvicorn..."
exec uvicorn linx.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: Reescrever o `Dockerfile`**

Conteúdo de `saas_backend/Dockerfile`:

```dockerfile
# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true \
    && poetry install --without dev --no-root --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/.venv ./.venv
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY docker-entrypoint.sh ./docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

RUN chmod +x ./docker-entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000 50051

ENTRYPOINT ["./docker-entrypoint.sh"]
```

> **Decisão:** `--no-root` evita que o Poetry instale o pacote `linx` (sem os arquivos `static/` e `templates/`, que não entram no wheel). O `PYTHONPATH=/app/src` faz `linx.main:app` importar direto de `/app/src/linx`, onde os HTML/CSS existem. Isso é o que garante que `main.py` encontre `static/` e `templates/` via `Path(__file__).parent`.

- [ ] **Step 3: Buildar a imagem e verificar**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend
docker build -t linx-saas-backend:dev .
```
Expected: build conclui com `Successfully tagged linx-saas-backend:dev`.

- [ ] **Step 4: Verificar que o entrypoint e as dependências estão na imagem**

Run:
```bash
docker run --rm --entrypoint sh linx-saas-backend:dev -c "which alembic uvicorn && test -f /app/docker-entrypoint.sh && test -d /app/migrations/versions && ls /app/src/linx/templates/index.html"
```
Expected: imprime os caminhos de `alembic` e `uvicorn` e o `ls` mostra `/app/src/linx/templates/index.html` sem erro.

- [ ] **Step 5: Commit**

```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git add saas_backend/Dockerfile saas_backend/docker-entrypoint.sh
git commit -m "feat(deploy): Dockerfile multi-stage e entrypoint com migrations"
```

---

## Task 3: `.env.example`

**Files:**
- Create: `saas_backend/.env.example`

- [ ] **Step 1: Criar o arquivo**

Conteúdo de `saas_backend/.env.example`:

```dotenv
POSTGRES_USER=linx
POSTGRES_PASSWORD=change-me-in-production
POSTGRES_DB=linx
DATABASE_URL=postgresql+psycopg://linx:change-me-in-production@db:5432/linx
DB_CONNECT_TIMEOUT=5
GRPC_HOST=0.0.0.0
GRPC_PORT=50051
```

> O host do banco é `db` (nome do serviço no Compose), não `localhost`. As variáveis `POSTGRES_*` são lidas pelo serviço `db`; `DATABASE_URL`/`DB_CONNECT_TIMEOUT`/`GRPC_*` são lidas pelo app via `pydantic-settings` (`linx/core/config.py`).

- [ ] **Step 2: Confirmar que `.env` está ignorado pelo git**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git check-ignore -v saas_backend/.env
```
Expected: imprime a regra do `.gitignore` que casa com `.env` (ex.: `.env:7:.env`).

- [ ] **Step 3: Commit**

```bash
git add saas_backend/.env.example
git commit -m "docs(deploy): adiciona .env.example do saas_backend"
```

---

## Task 4: `docker-compose.prod.yml`

**Files:**
- Create: `saas_backend/docker-compose.prod.yml`

- [ ] **Step 1: Criar o arquivo**

Conteúdo de `saas_backend/docker-compose.prod.yml`:

```yaml
services:
  db:
    image: postgres:15-alpine
    restart: unless-stopped
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-linx}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-linx}
      POSTGRES_DB: ${POSTGRES_DB:-linx}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U ${POSTGRES_USER:-linx} -d ${POSTGRES_DB:-linx}
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    ports:
      - "8000:8000"
      - "50051:50051"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s

volumes:
  pgdata:
```

> O Postgres **não** publica a porta `5432` (acessível apenas pela rede interna do Compose). O app publica `8000` (REST) e `50051` (gRPC).

- [ ] **Step 2: Validar a sintaxe do Compose**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend
cp .env.example .env
docker compose -f docker-compose.prod.yml config
```
Expected: o Compose imprime o YAML resolvido (sem erros) e mostra `restart: unless-stopped` nos dois serviços, `8000:8000` e `50051:50051` no app.

- [ ] **Step 3: Commit**

```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git add saas_backend/docker-compose.prod.yml
git commit -m "feat(deploy): docker-compose de producao (app + postgres)"
```

---

## Task 5: `scripts/deploy.sh`

**Files:**
- Create: `saas_backend/scripts/deploy.sh`

- [ ] **Step 1: Criar o diretório e o script**

Conteúdo de `saas_backend/scripts/deploy.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and set a strong POSTGRES_PASSWORD." >&2
  exit 1
fi

echo "Pulling latest code..."
git pull

echo "Building and starting containers..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Status:"
docker compose -f docker-compose.prod.yml ps
```

- [ ] **Step 2: Tornar executável e validar sintaxe**

Run:
```bash
chmod +x /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend/scripts/deploy.sh
bash -n /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend/scripts/deploy.sh
```
Expected: `bash -n` não imprime nada (sintaxe válida).

- [ ] **Step 3: Commit**

```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git add saas_backend/scripts/deploy.sh
git commit -m "feat(deploy): script de deploy do saas_backend"
```

---

## Task 6: Documentar no `README.md`

**Files:**
- Modify: `saas_backend/README.md` (adicionar seção antes de `## 📦 Dependências do projeto`, linha ~294)

- [ ] **Step 1: Inserir a seção de Deploy**

Adicione o bloco abaixo imediatamente antes da linha `## 📦 Dependências do projeto`:

````markdown
## 🚀 Deploy (produção / EC2)

O deploy de produção usa `docker-compose.prod.yml` (serviços `app` + `db`) e a imagem
construída pelo `Dockerfile`. O entrypoint aplica as migrations do Alembic e sobe o
Uvicorn, que também inicia o servidor gRPC.

### Variáveis de ambiente

Copie o template e ajuste a senha:

```bash
cd saas_backend
cp .env.example .env
```

| Variável             | Descrição                                                        | Default no exemplo              |
| -------------------- | ---------------------------------------------------------------- | ------------------------------- |
| `POSTGRES_USER`      | Usuário do Postgres do MVP.                                      | `linx`                          |
| `POSTGRES_PASSWORD`  | Senha do Postgres (troque em produção).                          | `change-me-in-production`       |
| `POSTGRES_DB`        | Banco do Postgres.                                               | `linx`                          |
| `DATABASE_URL`       | URL SQLAlchemy; host = `db` (serviço do Compose).                | `postgresql+psycopg://linx:...@db:5432/linx` |
| `DB_CONNECT_TIMEOUT` | Timeout de conexão com o banco (segundos).                       | `5`                             |
| `GRPC_HOST`          | Endereço de bind do servidor gRPC.                               | `0.0.0.0`                       |
| `GRPC_PORT`          | Porta do servidor gRPC.                                          | `50051`                         |

> O `.env` é ignorado pelo git; nunca o versione.

### Subir localmente (validar a stack de produção)

```bash
cd saas_backend
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
curl -i http://localhost:8000/health
```

Resposta esperada (`200`):

```json
{"status":"ok","db":true,"grpc":true}
```

### Runbook — EC2 `t3.small`

1. **Criar a instância:** EC2 `t3.small`, Ubuntu 22.04+ (ou Amazon Linux 2), com IP
   público e um keypair SSH.
2. **Security Group (inbound):**
   - `22` (SSH) — restrito ao seu IP;
   - `8000` (REST) — `0.0.0.0/0`;
   - `50051` (gRPC) — `0.0.0.0/0` (ou IP do Client Agent).
3. **Instalar Docker e Compose plugin:**
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin
   sudo usermod -aG docker "$USER" && newgrp docker
   ```
4. **Clonar o repositório e configurar o ambiente:**
   ```bash
   git clone https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus.git
   cd LINX-LoRaWAN-Intelligence-Nexus
   git checkout develop
   cd saas_backend
   cp .env.example .env
   # edite .env e defina uma POSTGRES_PASSWORD forte
   ```
5. **Subir a stack:**
   ```bash
   ./scripts/deploy.sh
   ```
6. **Verificar de fora da AWS:**
   ```bash
   curl -i http://<ec2-ip>:8000/health
   ```
   Expected: `200` com `{"status":"ok","db":true,"grpc":true}`.
````

- [ ] **Step 2: Conferir a renderização das tabelas**

Run:
```bash
grep -n "Deploy (produção / EC2)\|Runbook — EC2" /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend/README.md
```
Expected: as duas linhas aparecem.

- [ ] **Step 3: Commit**

```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git add saas_backend/README.md
git commit -m "docs(deploy): runbook de deploy do saas_backend na EC2"
```

---

## Task 7: Verificação end-to-end local (prova da issue)

**Files:** nenhum (apenas execução).

- [ ] **Step 1: Subir a stack a partir de um estado limpo**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend
cp .env.example .env
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```
Expected: os serviços `db` e `app` são criados e iniciam.

- [ ] **Step 2: Confirmar que o banco ficou saudável e o app subiu**

Run:
```bash
docker compose -f docker-compose.prod.yml ps
```
Expected: `db` com `(healthy)` e `app` com `Up` (pode levar ~20s até `(healthy)`). Política `restart: unless-stopped` visível no `docker inspect` (Step 5).

- [ ] **Step 3: Verificar que as migrations rodaram**

Run:
```bash
docker compose -f docker-compose.prod.yml logs app | grep -i "migrations\|Running upgrade"
```
Expected: aparece `Applying database migrations...` e uma linha de upgrade do Alembic (ex.: `Running upgrade  -> 0c14cfa628c3, initial 4 tables`).

- [ ] **Step 4: Verificar o critério de aceite — `/health` = 200**

Run:
```bash
curl -i http://localhost:8000/health
```
Expected:
```
HTTP/1.1 200 OK
...
{"status":"ok","db":true,"grpc":true}
```

- [ ] **Step 5: Verificar a política de restart**

Run:
```bash
docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' $(docker compose -f docker-compose.prod.yml ps -q)
```
Expected: os dois containers imprimem `unless-stopped`.

- [ ] **Step 6: Verificar que a porta gRPC está aceitando conexões**

Run:
```bash
docker compose -f docker-compose.prod.yml exec app python -c "import socket; s=socket.create_connection(('127.0.0.1',50051),2); print('grpc ok'); s.close()"
```
Expected: `grpc ok`.

- [ ] **Step 7: Derrubar a stack (sem apagar o volume, para simular produção)**

Run:
```bash
docker compose -f docker-compose.prod.yml down
```
Expected: containers removidos, volume `pgdata` preservado.

---

## Task 8: Garantir que o CI continua verde

**Files:** nenhum.

- [ ] **Step 1: Rodar lint e testes do backend**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx/saas_backend
poetry run task lint
poetry run pytest --cov=src --cov-fail-under=70
```
Expected: lint sem erros; testes passam e cobertura ≥ 70%. (Não houve mudança de código Python, então isso é uma regressão check.)

- [ ] **Step 2: Se algo falhar, corrigir antes de seguir**

> Nenhuma alteração de código é esperada nesta issue. Se o lint acusar formatação, rode `poetry run task lint` (formata) e commite a correção.

---

## Task 9: Commit final e PR

**Files:** nenhum.

- [ ] **Step 1: Revisar o diff completo do branch**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx
git status --short
git log --oneline develop..HEAD
```
Expected: apenas os arquivos desta issue e commits `feat(deploy)`/`chore(deploy)`/`docs(deploy)`.

- [ ] **Step 2: (Opcional) Abrir o PR para `develop`**

Run (somente quando o usuário pedir):
```bash
git push -u origin issue30_deploy_saas_backend
gh pr create --base develop --title "feat(devops): deploy SaaS Backend on EC2 t3.small (Docker Compose)" --body "Closes #30"
```
Expected: PR criado com a URL retornada.

---

## Task 10: Deploy real na AWS (execução futura pelo usuário)

> Esta task **não** é executada agora. Só é feita quando o usuário tiver a EC2.

**Files:** nenhum.

- [ ] **Step 1: Provisionar a EC2** conforme o runbook do README (t3.small, keypair, Security Group 22/8000/50051).
- [ ] **Step 2: Instalar Docker** na instância.
- [ ] **Step 3: Clonar o repo e criar o `.env`** (senha forte).
- [ ] **Step 4: Rodar `./scripts/deploy.sh`.**
- [ ] **Step 5: Validar de fora:** `curl -i http://<ec2-ip>:8000/health` → `200 {"status":"ok","db":true,"grpc":true}`.
- [ ] **Step 6: Fechar a issue #30** com a evidência do `curl`.

---

## Self-Review

**1. Cobertura dos critérios de aceite da issue #30:**
- Backend acessível via IP público na porta 8000 → Tasks 4, 10 (publicação `8000:8000` + runbook). ✔
- `GET /health` retorna `200` a partir da internet → Task 7, Step 4 (local) e Task 10, Step 5 (AWS). ✔
- Container sobe com `restart: unless-stopped` → Task 4 (YAML) e Task 7, Step 5 (verificação). ✔
- Verificação `curl http://<ec2-ip>:8000/health` → Task 10, Step 5. ✔
- Extra (critério da Sprint 2): porta gRPC 50051 exposta → Tasks 4 e 7, Step 6. ✔

**2. Placeholders:** nenhum `TBD`/`TODO`; todos os arquivos têm conteúdo completo.

**3. Consistência:** host do banco é `db` em `.env.example`, `docker-compose.prod.yml` e README; porta gRPC `50051` igual em `.env.example`, Compose e `config.py`; `DATABASE_URL` usa `postgresql+psycopg` (compatível com `db/base.py`).
