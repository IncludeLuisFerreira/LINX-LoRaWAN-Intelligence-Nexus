<div align="center">

<img src="docs/logo.svg" alt="LINX" width="150">

# LINX — LoRaWAN Intelligence Nexus

Plataforma SaaS IoT distribuída para dados LoRaWAN, com isolamento por aplicação.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

[![Backend CI](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/actions/workflows/frontend-ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![LoRaWAN](https://img.shields.io/badge/radio-LoRaWAN%20AU915-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

</div>

## Sobre o Projeto

O **LINX** é uma plataforma SaaS IoT para aquisição, processamento e visualização de dados de dispositivos LoRaWAN, hospedada 100% em nuvem (AWS). Ele resolve o problema das soluções IoT B2B que exigem infraestrutura local complexa, centralizando processamento e telemetria na nuvem e entregando um ambiente Docker isolado por aplicação. O público-alvo são organizações B2B — agricultura de precisão, indústria, logística e integradores de IoT — que precisam monitorar dispositivos sem manter servidores no local.

## Tech Stack

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.12 · FastAPI · gRPC · SQLAlchemy · Alembic |
| Frontend | React 19 · Vite · TypeScript · Tailwind CSS |
| Dados | PostgreSQL 15 · TimescaleDB |
| Conectividade IoT | ChirpStack v4 · LoRaWAN (AU915) · MQTT |
| Infraestrutura | Docker Compose · AWS · Nginx |
| Documentação | MkDocs Material · Astro |

## Quick Start

```bash
# 1. Clonar
git clone https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus.git
cd LINX-LoRaWAN-Intelligence-Nexus

# 2. Subir a stack LoRaWAN (ChirpStack + MQTT + PostgreSQL)
make up

# 3. Backend do plano de controle (REST :8000 + gRPC :50051)
cd linx_core
poetry install
poetry -C shared install
poetry -C services/identity_api install
poetry -C services/agent_bridge install
cp .env.example .env        # ajuste POSTGRES_PASSWORD e CHIRPSTACK_API_TOKEN
poetry run task run

# 4. Dashboard web (opcional, em outro terminal)
cd ../client/frontend
npm install
npm run dev
```

> ChirpStack UI em `http://localhost:8080` (`admin`/`admin`). REST do core em `http://localhost:8000` (`/docs`). Dashboard em `http://localhost:5173`.

## Stacks (Makefile)

Cada compose do repositório tem um target `up-<stack>` (e `down-<stack>` /
`logs-<stack>`). `make up` continua subindo só a infraestrutura base.

| Target | Compose | Conteúdo |
| --- | --- | --- |
| `make up` / `up-infra` | `infra/docker-compose.yml` | ChirpStack v4 + MQTT + PostgreSQL |
| `make up-base` | `infra/docker-compose.base.yml` | Base de dev (PostgreSQL + Redis + Mosquitto) |
| `make up-core` | `linx_core/docker-compose.yml` | Plano de controle (identity_api + agent_bridge + db) |
| `make up-client` | `client/docker-compose.yml` | Ambiente isolado (frontend + telemetry_consumer + TimescaleDB) |
| `make up-deploy` | `deploy/docker-compose.yml` | Stack full-stack (nginx + TLS + todos os serviços) |
| `make up-client-agent` | `deploy/docker-compose.client-agent.yml` | Client Agent isolado (ver nota abaixo) |
| `make test-integration` | `tests/integration/run.sh` | Testes de integração ponta-a-ponta |

> `make up-client-agent` exige um `AGENT_SERVICE_TOKEN` real (não placeholder)
> no `deploy/.env` e um `agent_bridge` alcançável. O default
> `SAAS_GRPC_HOST=agent_bridge:50051` só resolve com a stack de
> `deploy/docker-compose.yml` em execução; para outro host, defina
> `SAAS_GRPC_HOST` no ambiente antes de subir o target.

> `make help` lista a matriz completa. Rode `make down-<stack>` para derrubar
> uma stack específica.

## Estrutura

```
LINX/
├── linx_core/     # Plano de controle (REST FastAPI + gRPC AgentBridge)
├── middleware/    # Middleware: roteamento de uplinks (routing) + agente por tenant (client_agent)
├── client/        # Ambiente isolado do cliente (frontend + telemetry_consumer + TimescaleDB)
├── infra/         # Stack ChirpStack v4 (gateway bridge, MQTT, PostgreSQL)
├── deploy/        # Compose full-stack (nginx, TLS, todos os serviços)
├── proto/         # Contrato gRPC compartilhado (linx_agent.proto)
├── docs/          # Documentação (MkDocs)
└── website/       # Site institucional (Astro)
```

> Documentação completa: [`PRD_PLATAFORMA_IOT.md`](PRD_PLATAFORMA_IOT.md) · [`docs/`](docs/)

## Contribuição

Instale as dependências da raiz (uma vez) para habilitar o hook de pre-commit:

```bash
npm install          # husky + lint-staged na raiz
pipx install ruff    # ou deixe `ruff` no PATH
```

O `.husky/pre-commit` roda `lint-staged` com a config do `package.json` da
raiz: arquivos do frontend passam por `prettier` + `oxlint`, e arquivos
Python por `ruff check --fix`. O hook cobre todo o monorepo (não só
`client/frontend`).
