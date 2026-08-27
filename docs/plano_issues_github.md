# Plano de Setup do GitHub — LINX

> Gerado automaticamente. Revisar antes de aplicar.

## 1. Milestones (8)

| # | Título | Data limite | Descrição |
|---|---|---|---|
| 1 | Sprint 1 | 2026-09-09 | Fundação: contratos, CI/CD, infra local rodando |
| 2 | Sprint 2 | 2026-09-23 | SaaS Backend + Client Agent na AWS, gRPC funcionando |
| 3 | Sprint 3 | 2026-10-07 | ChirpStack integrado, uplink ponta-a-ponta, WebSocket |
| 4 | Sprint 4 | 2026-10-21 | Multi-tenant real: provisionamento automático de Docker por app |
| 5 | Sprint 5 | 2026-11-04 | Autenticação JWT/OAuth2, RBAC, TLS em todas as camadas |
| 6 | Sprint 6 | 2026-11-18 | Motor de regras, downlink, alertas (Telegram/Email) |
| 7 | Sprint 7 | 2026-12-02 | Resiliência: retry, circuit breaker, DLQ, graceful shutdown |
| 8 | Sprint 8 | 2026-12-14 | Observabilidade, hardening, QR Code, demo final |

## 2. Labels (12)

| Label | Cor | Descrição |
|---|---|---|
| `sprint-1` | `#0e8a16` | Sprint 1 — Fundação e Contratos |
| `sprint-2` | `#fbca04` | Sprint 2 — Dois Serviços na AWS com gRPC |
| `sprint-3` | `#d93f0b` | Sprint 3 — ChirpStack, Uplink e WebSocket |
| `sprint-4` | `#b60205` | Sprint 4 — Multi-Tenant Real |
| `sprint-5` | `#5319e7` | Sprint 5 — Autenticação, RBAC e TLS |
| `sprint-6` | `#006b75` | Sprint 6 — Motor de Regras e Downlink |
| `sprint-7` | `#1d76db` | Sprint 7 — Resiliência |
| `sprint-8` | `#d4c5f9` | Sprint 8 — Observabilidade e Hardening |
| `frontend` | `#61dafb` | Código do frontend (React/Vite/TS) |
| `backend` | `#2ea043` | Código de backend (FastAPI/gRPC/agente) |
| `devops` | `#f9d0c4` | Infra, CI/CD, deploy, Docker |
| `docs` | `#d876e3` | Documentação |

## 3. Assignees

- Aluno 1 → `Lynnes42` (área default: frontend)
- Aluno 2 → `IncludeLuisFerreira` (área default: backend)
- Aluno 3 → `deny759` (área default: backend)

## 4. Issues por Sprint

### Sprint 1 — Fundação e Contratos (22 issues)

#### `feat(frontend): scaffold React + Vite + TypeScript + TailwindCSS`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Ponto de partida do módulo frontend; sem scaffold funcional nenhuma tela pode ser construída.

## Critérios de aceite
- [ ] Projeto inicializado em frontend/ com React, Vite, TypeScript e TailwindCSS
- [ ] npm run build compila sem erros
- [ ] Estrutura base criada (pages/, components/, services/, hooks/)

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)

#### `chore(frontend): configure ESLint + Prettier + husky pre-commit`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Garante padrão de código e previne commits com erros de lint/formatação.

## Critérios de aceite
- [ ] ESLint configurado com regras React + TypeScript
- [ ] Prettier configurado
- [ ] husky executa lint no pre-commit

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(frontend): routing structure (login, orgs, apps, devices, dashboard)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Define a navegação base do SaaS; as rotas são a espinha dorsal das telas.

## Critérios de aceite
- [ ] React Router configurado
- [ ] Rotas /login, /orgs, /apps/:id, /devices e /dashboard/:appId existem
- [ ] Rota inexistente cai em fallback

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(frontend): responsive layout shell (Sidebar + AppBar + ContentArea)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Shell responsivo compartilhado por todas as telas autenticadas.

## Critérios de aceite
- [ ] Componentes Sidebar, AppBar e ContentArea criados
- [ ] Layout responsivo (mobile/desktop)
- [ ] Menu destaca a rota ativa

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(frontend): login screen with local auth mock`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Tela de login com autenticação mockada para desbloquear o fluxo antes do backend real.

## Critérios de aceite
- [ ] Formulário de login
- [ ] Mock de autenticação local
- [ ] Redireciona para /orgs após login

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): axios instance with baseURL and JWT interceptors`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Cliente HTTP centralizado pronto para autenticação JWT, evitando repetição.

## Critérios de aceite
- [ ] Axios instance com baseURL configurável
- [ ] Interceptor de request injeta Authorization quando há token
- [ ] Interceptor de response trata 401

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): openapi-stub.yaml with expected REST contracts`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `frontend`

## Contexto
Contrato REST acordado com o Aluno 2 para desenvolvimento paralelo contra mock.

## Critérios de aceite
- [ ] Arquivo openapi-stub.yaml criado
- [ ] Contratos de organizações e aplicações definidos
- [ ] Validado em conjunto com o Aluno 2

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-001, RF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): scaffold FastAPI + Poetry project`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Base do SaaS Backend; define dependências e estrutura do serviço.

## Critérios de aceite
- [ ] Projeto FastAPI em saas_backend/
- [ ] Poetry com pyproject.toml
- [ ] Aplicação sobe localmente

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)

#### `feat(devops): docker-compose.base.yml (PostgreSQL 15, Redis 7, Mosquitto)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `devops`

## Contexto
Infraestrutura local de dados e mensageria para desenvolvimento e CI.

## Critérios de aceite
- [ ] docker-compose.base.yml em infra/
- [ ] Serviços PostgreSQL 15, Redis 7 e Mosquitto
- [ ] docker-compose -f infra/docker-compose.base.yml up sobe sem erros

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)

#### `feat(backend): SQLAlchemy models (organizations, applications, users, roles)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Modelos de domínio centrais com UUID como PK (nomeação de recursos).

## Critérios de aceite
- [ ] 4 models com id UUID PK
- [ ] Relacionamento organization → application definido
- [ ] Tipos SQLAlchemy 2.0

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-040](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): initial Alembic migration for 4 tables`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Versionamento do schema do PostgreSQL central.

## Critérios de aceite
- [ ] Migration inicial cria as 4 tabelas
- [ ] alembic upgrade head aplica com sucesso

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-040](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): CRUD REST for organizations /api/v1/orgs`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Primeiro endpoint REST público do SaaS (cadastro de organizações).

## Critérios de aceite
- [ ] POST/GET/PATCH/DELETE /api/v1/orgs
- [ ] Validação de payload
- [ ] Testes cobrindo o CRUD

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-001](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): CRUD REST for applications linked to org`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Aplicações pertencem a uma organização, com org_id FK.

## Critérios de aceite
- [ ] CRUD de /api/v1/applications
- [ ] org_id FK obrigatório
- [ ] Testes de integridade referencial

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-002](PRD_PLATAFORMA_IOT.md)

#### `ci(devops): GitHub Actions (black, flake8, mypy, pytest >=70%)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `devops`

## Contexto
CI verde é critério de aceite do sprint e garante qualidade em todos os commits.

## Critérios de aceite
- [ ] Workflow roda black, flake8, mypy e pytest
- [ ] Cobertura >= 70%
- [ ] CI verde em push/PR

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)

#### `feat(backend): deliver OpenAPI stub for frontend`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Dependência crítica para o Aluno 1 desenvolver em paralelo (prazo 03/09).

## Critérios de aceite
- [ ] OpenAPI stub entregue até 03/09
- [ ] Contratos de organizações e aplicações
- [ ] Aluno 1 consegue desenvolver contra o stub

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-001, RF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): scaffold client_agent_api and tenant_app_template`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Base dos serviços de agente e do template do tenant.

## Critérios de aceite
- [ ] client_agent_api/ e tenant_app_template/ com FastAPI
- [ ] Estrutura de pastas padronizada

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)

#### `feat(backend): TimescaleDB schema with telemetry hypertable`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Esquema de série temporal isolado por aplicação.

## Critérios de aceite
- [ ] schema.sql com hypertable telemetry
- [ ] Colunas: time, dev_eui, payload, rssi, snr
- [ ] create_hypertable aplicado

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-012](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): basic MQTT consumer for uplink events`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Consome uplinks do Mosquitto para iniciar o fluxo de telemetria.

## Critérios de aceite
- [ ] Consumidor paho-mqtt
- [ ] Subscribe em application/+/device/+/event/up
- [ ] Loga o payload recebido

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): define proto/saas_agent.proto (AgentBridge)`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Contrato gRPC entre SaaS Backend e Client Agent (dependência crítica).

## Critérios de aceite
- [ ] proto/saas_agent.proto criado
- [ ] rpc GetAppConfig e IngestTelemetry definidos
- [ ] Mensagens AppConfig, TelemetryEvent e Ack definidas

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): generate Python gRPC stubs`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `backend`

## Contexto
Gera os stubs a partir do .proto para uso nos serviços.

## Critérios de aceite
- [ ] Stubs Python gerados
- [ ] Importáveis em ambos os serviços

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): multi-stage Dockerfile for client_agent_api`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `devops`

## Contexto
Imagem Docker enxuta para o agente.

## Critérios de aceite
- [ ] Dockerfile multi-stage
- [ ] docker build conclui com sucesso

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)

#### `feat(devops): tenant docker-compose (client_agent_api + timescaledb)`
- **Assignee:** deny759 · **Milestone:** Sprint 1 · **Labels:** `sprint-1`, `devops`

## Contexto
Compose do ambiente isolado do tenant.

## Critérios de aceite
- [ ] docker-compose.yml do tenant
- [ ] Serviços client_agent_api + timescaledb
- [ ] Sobe sem erros

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 1 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-012](PRD_PLATAFORMA_IOT.md)

### Sprint 2 — Dois Serviços na AWS com gRPC (17 issues)

#### `feat(frontend): organization registration screen consuming POST /api/v1/orgs`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `frontend`

## Contexto
Cadastro de organização contra o backend real na AWS.

## Critérios de aceite
- [ ] Formulário de organização
- [ ] Chama POST /api/v1/orgs
- [ ] Trata sucesso/erro

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-001](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): application registration screen with organization select`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `frontend`

## Contexto
Cadastro de aplicação vinculado a uma organização.

## Critérios de aceite
- [ ] Formulário de aplicação
- [ ] Select de Organization
- [ ] Envia org_id

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): frontend Dockerfile (nginx alpine serving static build)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
Empacota o frontend para deploy.

## Critérios de aceite
- [ ] Dockerfile com nginx alpine
- [ ] Serve o build estático

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(devops): deploy-frontend.sh (build → push → deploy EC2/S3+CloudFront)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
Automatiza o deploy do frontend na AWS.

## Critérios de aceite
- [ ] Script deploy-frontend.sh
- [ ] Fluxo build → push → deploy

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(devops): nginx local routing /api/* → SaaS Backend AWS`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
Permite desenvolvimento local apontando para o backend remoto.

## Critérios de aceite
- [ ] Nginx local roteia /api/* para o backend AWS

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(backend): gRPC server with GetAppConfig`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Servidor gRPC que devolve a configuração da aplicação para o Client Agent.

## Critérios de aceite
- [ ] grpc_server.py com GetAppConfig
- [ ] Retorna db_host, db_port e mqtt_topic

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): GET /health (DB + gRPC server status)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Health check do serviço.

## Critérios de aceite
- [ ] GET /health
- [ ] Reporta status do DB e do gRPC server

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 2](SPRINTS_BACKLOG.md)

#### `feat(devops): deploy SaaS Backend on EC2 t3.small (Docker Compose)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
Deploy real do backend na AWS.

## Critérios de aceite
- [ ] EC2 t3.small com Docker Compose
- [ ] App + PostgreSQL local rodando

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 2](SPRINTS_BACKLOG.md)

#### `feat(devops): AWS Security Group (8000, 50051, 22)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
Exposição controlada das portas.

## Critérios de aceite
- [ ] Security Group com inbound 8000, 50051 e 22

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): nginx with TLS (Let's Encrypt / self-signed dev)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
HTTPS na borda do backend.

## Critérios de aceite
- [ ] Nginx com TLS configurado
- [ ] Certificado válido ou self-signed para dev

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): device_routes table (dev_eui, app_id, agent_endpoint)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Base para roteamento futuro de telemetria.

## Critérios de aceite
- [ ] Tabela device_routes criada
- [ ] Colunas dev_eui, app_id e agent_endpoint

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): gRPC client calling GetAppConfig on startup`
- **Assignee:** deny759 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Client Agent obtém a configuração da aplicação do SaaS no boot.

## Critérios de aceite
- [ ] grpc_client.py conecta na porta 50051
- [ ] Chama GetAppConfig no startup

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /ingest (validate schema, persist TimescaleDB)`
- **Assignee:** deny759 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Endpoint de ingestão de telemetria normalizada.

## Critérios de aceite
- [ ] POST /ingest
- [ ] Valida schema JSON
- [ ] Persiste no TimescaleDB

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): pipeline Mosquitto → mqtt_consumer → POST /ingest → TimescaleDB`
- **Assignee:** deny759 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Fluxo ponta-a-ponta de ingestão no agente.

## Critérios de aceite
- [ ] Pipeline completo funcionando

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): deploy Client Agent on second EC2 (or port 8001)`
- **Assignee:** deny759 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `devops`

## Contexto
Deploy do agente em instância separada.

## Critérios de aceite
- [ ] Client Agent rodando na AWS
- [ ] Porta acessível

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 3](SPRINTS_BACKLOG.md)

#### `feat(backend): log AppConfig received via gRPC (proof of communication)`
- **Assignee:** deny759 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `backend`

## Contexto
Prova documentada da comunicação gRPC.

## Critérios de aceite
- [ ] Log mostra AppConfig recebido via gRPC

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `docs(backend): README with curl for create org + ingest telemetry`
- **Assignee:** deny759 · **Milestone:** Sprint 2 · **Labels:** `sprint-2`, `docs`

## Contexto
Documentação reprodutível dos fluxos.

## Critérios de aceite
- [ ] README com curl criando org via SaaS REST
- [ ] curl ingerindo telemetria via Client Agent

## Stack afetado
docs

## Referências
- [SPRINTS_BACKLOG.md — Sprint 2 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC01, UC06](PRD_PLATAFORMA_IOT.md)

### Sprint 3 — ChirpStack, Uplink Ponta-a-Ponta e WebSocket (14 issues)

#### `feat(frontend): QR Code reader (html5-qrcode) parsing TR005`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `frontend`

## Contexto
Onboarding plug-and-play lendo o QR Code TR005 do sensor.

## Critérios de aceite
- [ ] Integração html5-qrcode
- [ ] Parse de SchemaID, JoinEUI, DevEUI e AppKey

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-021](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): onboarding wizard (scan → confirm → select app → submit)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `frontend`

## Contexto
Fluxo guiado de cadastro de dispositivo.

## Critérios de aceite
- [ ] Wizard de 3 passos
- [ ] Submit envia os dados do device

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-021](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): dashboard line chart (Recharts/Chart.js) consuming REST history`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `frontend`

## Contexto
Visualização do histórico de telemetria.

## Critérios de aceite
- [ ] Gráfico de linha (Recharts ou Chart.js)
- [ ] Consome histórico REST

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-030](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): connect dashboard to Client Agent WebSocket (real-time)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `frontend`

## Contexto
Atualização do gráfico em tempo real.

## Critérios de aceite
- [ ] Dashboard conecta ao WebSocket
- [ ] Atualiza o gráfico em tempo real

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-030](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): polling fallback GET /telemetry every 5s`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `frontend`

## Contexto
Resiliência quando o WebSocket cai.

## Critérios de aceite
- [ ] Fallback de polling a cada 5s
- [ ] Consome GET /telemetry

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-031](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): ChirpStack gRPC client (chirpstack-api)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Integração com o Network Server via gRPC.

## Critérios de aceite
- [ ] chirpstack_client.py usando chirpstack-api

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-022](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /api/v1/devices (validate, save, provision ChirpStack)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Cadastro de device no PostgreSQL global + ChirpStack.

## Critérios de aceite
- [ ] Valida payload
- [ ] Salva devices com dev_eui UNIQUE e app_key criptografado
- [ ] Provisiona no ChirpStack via gRPC

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-020, RF-021, RF-022](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): routing service (uplink MQTT → device_routes → client agent)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Roteamento de uplink para o endpoint correto do agente.

## Critérios de aceite
- [ ] Consulta device_routes
- [ ] Encaminha para o endpoint correto

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): ChirpStack Application publishing to uplink topic`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `devops`

## Contexto
Configura a publicação MQTT no tópico padrão.

## Critérios de aceite
- [ ] ChirpStack publica em application/{app_id}/device/{dev_eui}/event/up

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-022](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): parse ChirpStack v4 uplink payload`
- **Assignee:** deny759 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Extração dos campos do uplink do ChirpStack.

## Critérios de aceite
- [ ] Extrai devEUI, fCnt, rxInfo e object

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-022](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): normalize telemetry object to TimescaleDB record`
- **Assignee:** deny759 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Transforma o payload em registro de série temporal.

## Critérios de aceite
- [ ] Normaliza object para registro no TimescaleDB

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-012](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): GET /api/v1/telemetry/{dev_eui} (cursor pagination)`
- **Assignee:** deny759 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Consulta de histórico paginada.

## Critérios de aceite
- [ ] Endpoint com from/to/limit
- [ ] Paginação cursor-based

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC09](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): WebSocket /ws/telemetry/{app_id} broadcast`
- **Assignee:** deny759 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `backend`

## Contexto
Push em tempo real para clients conectados.

## Critérios de aceite
- [ ] @app.websocket /ws/telemetry/{app_id}
- [ ] Broadcast ao chegar nova mensagem MQTT

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-030](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): docker-compose with full ChirpStack v4`
- **Assignee:** deny759 · **Milestone:** Sprint 3 · **Labels:** `sprint-3`, `devops`

## Contexto
Sobe o ChirpStack completo localmente.

## Critérios de aceite
- [ ] docker-compose com ChirpStack v4 completo

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 3 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-022](PRD_PLATAFORMA_IOT.md)

### Sprint 4 — Multi-Tenant Real: Provisionamento Automático (15 issues)

#### `feat(frontend): provisioning status indicator (PENDING→PROVISIONING→RUNNING→ERROR)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `frontend`

## Contexto
Feedback visual do provisionamento da aplicação.

## Critérios de aceite
- [ ] Indicador visual dos 4 estados

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): polling GET /applications/{app_id}/status every 3s`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `frontend`

## Contexto
Acompanhamento do provisionamento até RUNNING.

## Critérios de aceite
- [ ] Polling a cada 3s até status RUNNING

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): devices screen (list, status, last telemetry)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `frontend`

## Contexto
Listagem de dispositivos da aplicação.

## Critérios de aceite
- [ ] Lista devices
- [ ] Status online/offline
- [ ] Última telemetria

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-020](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): UUID display with copy button`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `frontend`

## Contexto
Exibir UUID dos recursos com ação de copiar.

## Critérios de aceite
- [ ] Exibe UUID
- [ ] Botão copiar

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-040](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /applications/{app_id}/provision (docker-py)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Provisionamento automático do container do tenant.

## Critérios de aceite
- [ ] docker run a partir de tenant_app_template
- [ ] Porta dinâmica 8100-9100
- [ ] Env injetadas (APP_ID, DB_PASSWORD, MQTT_TOPIC)

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): application_instances table`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Registro das instâncias provisionadas.

## Critérios de aceite
- [ ] Tabela com container_id, host, port, status e provisioned_at

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): auto-trigger provision on app creation (BackgroundTasks)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Criação de aplicação dispara provisionamento em background.

## Critérios de aceite
- [ ] BackgroundTasks chama provision ao criar app

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): GET /applications/{app_id}/status (docker inspect)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Consulta do status do container.

## Critérios de aceite
- [ ] Retorna status via docker inspect

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): enforce UUID v4 on all resources`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Garante 100% UUID v4 nos recursos.

## Critérios de aceite
- [ ] Constraint UNIQUE + validação em middleware

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-040](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): update device_routes with provisioned endpoint`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Atualiza o roteamento com o endpoint real do container.

## Critérios de aceite
- [ ] device_routes atualizado com endpoint provisionado

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): publish tenant_app_template image to ECR/Docker Hub`
- **Assignee:** deny759 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `devops`

## Contexto
Imagem do tenant disponível para provisionamento.

## Critérios de aceite
- [ ] Imagem publicada no ECR (ou Docker Hub)

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): Client Agent receives APP_ID and MQTT_TOPIC via env`
- **Assignee:** deny759 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Configuração do agente por variável de ambiente.

## Critérios de aceite
- [ ] Lê APP_ID e MQTT_TOPIC no startup

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): network isolation (dedicated bridge per app)`
- **Assignee:** deny759 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `devops`

## Contexto
Isolamento de rede entre tenants.

## Critérios de aceite
- [ ] Cada container em bridge dedicada por app

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-011, RF-012](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): tenant /health (TimescaleDB + MQTT consumer)`
- **Assignee:** deny759 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Health check do tenant.

## Critérios de aceite
- [ ] /health retorna status do TimescaleDB e do consumidor MQTT

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-011](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): isolation test script (2 apps, no data crossing)`
- **Assignee:** deny759 · **Milestone:** Sprint 4 · **Labels:** `sprint-4`, `backend`

## Contexto
Prova automatizada de isolamento entre tenants.

## Critérios de aceite
- [ ] Script cria 2 apps e publica em cada uma
- [ ] Verifica que os dados não se cruzam

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 4 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-013](PRD_PLATAFORMA_IOT.md)

### Sprint 5 — Autenticação, RBAC e TLS (17 issues)

#### `feat(frontend): full JWT login (access in memory, refresh httpOnly cookie)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `frontend`

## Contexto
Autenticação completa no frontend.

## Critérios de aceite
- [ ] POST /auth/login
- [ ] access_token em memória
- [ ] refresh_token em httpOnly cookie

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): AuthGuard (redirect to /login on expired token)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `frontend`

## Contexto
Proteção de rotas.

## Critérios de aceite
- [ ] Decodifica exp do JWT
- [ ] Redireciona para /login se expirado

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): <Can permission="device:create"> component`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `frontend`

## Contexto
Controle de UI baseado em permissão.

## Critérios de aceite
- [ ] Componente Can renderiza condicionalmente pela permissão

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-003](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): user management screen (list, invite, role, deactivate)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `frontend`

## Contexto
Gestão de usuários da organização.

## Critérios de aceite
- [ ] Listar, convidar, alterar papel e desativar

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-003](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): HTTPS on frontend deploy`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `devops`

## Contexto
TLS na borda do frontend.

## Critérios de aceite
- [ ] HTTPS via CloudFront ou Nginx + certificado

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): OAuth2 password flow (POST /auth/login JWT)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Emissão de JWT access/refresh.

## Critérios de aceite
- [ ] access token 15min, refresh token 7d

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): bcrypt password hashing (passlib rounds=12)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Hash seguro de senhas.

## Critérios de aceite
- [ ] passlib[bcrypt] com rounds=12

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /auth/refresh`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Renovação de access token.

## Critérios de aceite
- [ ] Valida refresh token e emite novo access

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): RBAC (permissions, user_roles, require_permission middleware)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Autorização em 100% dos endpoints.

## Critérios de aceite
- [ ] Tabelas permissions e user_roles
- [ ] Depends(require_permission) em todos os endpoints

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-003](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): TLS 1.3 on all endpoints`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `devops`

## Contexto
TLS em toda a borda.

## Critérios de aceite
- [ ] Let's Encrypt na AWS
- [ ] TLS 1.3

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): rate limiting (slowapi Redis)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Proteção contra abuso.

## Critérios de aceite
- [ ] 100 req/min por IP
- [ ] 10 req/min para /auth/login

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)

#### `feat(backend): invite user (POST /orgs/{org_id}/invite)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Convite com token TTL 48h no Redis.

## Critérios de aceite
- [ ] Gera token de convite com TTL 48h

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-003](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): Mosquitto TLS (8883, reject 1883 non-TLS)`
- **Assignee:** deny759 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `devops`

## Contexto
MQTT sobre TLS.

## Critérios de aceite
- [ ] Porta 8883 MQTT over TLS
- [ ] Rejeita conexões não-TLS na 1883

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): mTLS gRPC between Client Agent and SaaS`
- **Assignee:** deny759 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `devops`

## Contexto
Autenticação mútua gRPC.

## Critérios de aceite
- [ ] ssl_channel_credentials com ca.crt, client.crt e client.key

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): JWT validation middleware in Client Agent`
- **Assignee:** deny759 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Validação de JWT contra chave pública do SaaS.

## Critérios de aceite
- [ ] Middleware verifica Authorization: Bearer

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): /health protected by X-Service-Token`
- **Assignee:** deny759 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Proteção do health com token de serviço.

## Critérios de aceite
- [ ] /health requer X-Service-Token

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-005](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): encrypt app_key at rest (AES-256-GCM)`
- **Assignee:** deny759 · **Milestone:** Sprint 5 · **Labels:** `sprint-5`, `backend`

## Contexto
Criptografia de segredos em repouso.

## Critérios de aceite
- [ ] app_key criptografado AES-256-GCM no TimescaleDB

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 5 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

### Sprint 6 — Motor de Regras, Downlink e Alertas (13 issues)

#### `feat(frontend): rules screen (sensor_field, operator, threshold, action_type)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `frontend`

## Contexto
Criação de regras de negócio.

## Critérios de aceite
- [ ] Formulário com sensor_field, operator, threshold e action_type

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): alerts screen (table desc)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `frontend`

## Contexto
Listagem de alertas disparados.

## Critérios de aceite
- [ ] Tabela com alert_id, rule_id, dev_eui, triggered_at e message
- [ ] Ordenada desc

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC08](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): send command button (downlink manual) with JSON modal`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `frontend`

## Contexto
Downlink manual do operador.

## Critérios de aceite
- [ ] Botão Enviar Comando
- [ ] Modal com campo payload JSON

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): history screen with filters`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `frontend`

## Contexto
Consulta de histórico filtrada.

## Critérios de aceite
- [ ] Date range picker, select de dispositivo e tipo de métrica

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC09](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /api/v1/rules (persist + SyncRule gRPC)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Persistência e replicação de regras para o tenant.

## Critérios de aceite
- [ ] Persiste regra no PostgreSQL
- [ ] Replica via gRPC SyncRule

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /api/v1/downlinks (ChirpStack Enqueue)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Acionamento de downlink via ChirpStack.

## Critérios de aceite
- [ ] Valida permissão
- [ ] ChirpStack DeviceQueueService.Enqueue

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): notifications service (Telegram Bot API + SMTP)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Notificação por Telegram/Email.

## Critérios de aceite
- [ ] Integração Telegram Bot API
- [ ] SMTP email
- [ ] Configurável por aplicação

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC08](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): alerts table`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Registro de alertas disparados.

## Critérios de aceite
- [ ] Tabela alerts (id UUID, rule_id FK, dev_eui, triggered_at, message, notified)

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC08](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): rules engine (asteval, no native eval)`
- **Assignee:** deny759 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Motor de regras isolado por tenant.

## Critérios de aceite
- [ ] rules_engine.py usa asteval
- [ ] Avalia regras a cada telemetria inserida

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): publish rule_violated via gRPC (ReportViolation)`
- **Assignee:** deny759 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Notificação de violação ao SaaS.

## Critérios de aceite
- [ ] Publica rule_violated via gRPC ReportViolation

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): downlink_queue table`
- **Assignee:** deny759 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Fila de downlinks do tenant.

## Critérios de aceite
- [ ] Tabela downlink_queue (status ENUM pending/sent/failed)

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): async worker processing downlink_queue every 30s`
- **Assignee:** deny759 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Processamento assíncrono da fila.

## Critérios de aceite
- [ ] Worker a cada 30s
- [ ] Chama SaaS para enfileirar no ChirpStack

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): POST /rules/sync (gRPC receive rule)`
- **Assignee:** deny759 · **Milestone:** Sprint 6 · **Labels:** `sprint-6`, `backend`

## Contexto
Recepção de regra do SaaS no tenant.

## Critérios de aceite
- [ ] Endpoint gRPC recebe regra
- [ ] Persiste localmente

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 6 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — UC07](PRD_PLATAFORMA_IOT.md)

### Sprint 7 — Resiliência: Retry, Circuit Breaker e DLQ (14 issues)

#### `feat(frontend): axios retry on 5xx (3 tries, backoff 1s/2s/4s)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `frontend`

## Contexto
Resiliência no cliente HTTP.

## Critérios de aceite
- [ ] Retry automático em 5xx (3 tentativas)
- [ ] Backoff 1s/2s/4s

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): WebSocket reconnect with exponential backoff`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `frontend`

## Contexto
Reconexão automática do WebSocket.

## Critérios de aceite
- [ ] Backoff 1s,2s,4s,8s (max 30s)

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-031](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): offline mode indicator in header`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `frontend`

## Contexto
Feedback de indisponibilidade do backend.

## Critérios de aceite
- [ ] Indicador Modo Offline em 5xx/timeout

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): system status screen (GET /health all services)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `frontend`

## Contexto
Painel de saúde dos serviços.

## Critérios de aceite
- [ ] Consome /health de todos os serviços
- [ ] Exibe verde/vermelho

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): gRPC retry with tenacity exponential backoff`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Retry para chamadas gRPC ao ChirpStack.

## Critérios de aceite
- [ ] tenacity wait_exponential(min=4, max=60)
- [ ] Máx 5 tentativas

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): circuit breaker (pybreaker) for Client Agent`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Proteção contra falhas em cascata.

## Critérios de aceite
- [ ] Abre após 5 falhas
- [ ] Meio-aberto após 30s
- [ ] Fallback retorna 503

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): DLQ with Redis Streams (failed_events)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Nenhuma mensagem perdida silenciosamente.

## Critérios de aceite
- [ ] DLQ Redis Streams failed_events
- [ ] Mensagens que falharam após 3 retries

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-041](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): retry Docker provisioning (3 tries before ERROR)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Resiliência no provisionamento.

## Critérios de aceite
- [ ] 3 tentativas com backoff
- [ ] Marca ERROR após esgotar

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-010](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): PostgreSQL backup (pg_dump daily to S3)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `devops`

## Contexto
Backup automatizado do banco central.

## Critérios de aceite
- [ ] pg_dump diário para S3 via cron

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): retry MQTT publish (downlinks) → downlink_queue`
- **Assignee:** deny759 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Resiliência na publicação de downlinks.

## Critérios de aceite
- [ ] Se publish falhar, enfileira em downlink_queue

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): HEALTHCHECK in Dockerfile`
- **Assignee:** deny759 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `devops`

## Contexto
Health check do container.

## Critérios de aceite
- [ ] HEALTHCHECK curl -f /health || exit 1

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): graceful shutdown (SIGTERM handler)`
- **Assignee:** deny759 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Encerramento limpo do serviço.

## Critérios de aceite
- [ ] Fecha MQTT, flush de queries e encerra

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): publish container_down if tenant unresponsive 60s`
- **Assignee:** deny759 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Detecção de tenant indisponível.

## Critérios de aceite
- [ ] Publica container_down após 60s sem health

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): MQTT consumer auto-reconnect with backoff`
- **Assignee:** deny759 · **Milestone:** Sprint 7 · **Labels:** `sprint-7`, `backend`

## Contexto
Reconexão automática do consumidor.

## Critérios de aceite
- [ ] Reconecta com backoff se a conexão cair

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 7 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RF-042](PRD_PLATAFORMA_IOT.md)

### Sprint 8 — Observabilidade, Hardening e Demo Final (16 issues)

#### `feat(frontend): audit logs screen`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `frontend`

## Contexto
Visualização de logs de auditoria.

## Critérios de aceite
- [ ] Tela com timestamp, user, action, resource e ip_address

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): metrics dashboard (latency, active devices, alerts/hour)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `frontend`

## Contexto
Dashboard de métricas do sistema.

## Critérios de aceite
- [ ] Latência média, devices ativos e alertas/hora

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(frontend): polish UI (skeletons, empty states, mobile)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `frontend`

## Contexto
Acabamento de UX.

## Critérios de aceite
- [ ] Loading skeletons, empty states e responsividade mobile

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 1](SPRINTS_BACKLOG.md)

#### `feat(frontend): demo video (QR → telemetry → alert → downlink)`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `frontend`

## Contexto
Material de demonstração do MVP.

## Critérios de aceite
- [ ] Vídeo de 5-10 min do fluxo completo

## Stack afetado
frontend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — MVP §12](PRD_PLATAFORMA_IOT.md)

#### `docs(frontend): DEMO_SCRIPT.md`
- **Assignee:** Lynnes42 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `docs`

## Contexto
Roteiro da demonstração.

## Critérios de aceite
- [ ] docs/DEMO_SCRIPT.md passo-a-passo

## Stack afetado
docs

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 1](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — MVP §12](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): Prometheus metrics (/metrics)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `backend`

## Contexto
Métricas de latência, erro e throughput.

## Critérios de aceite
- [ ] prometheus-fastapi-instrumentator
- [ ] histogram/counter/gauge em /metrics

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): structured JSON logs (structlog)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `backend`

## Contexto
Logs estruturados.

## Critérios de aceite
- [ ] structlog com timestamp, level, correlation_id, service e message

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): X-Correlation-ID propagation`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `backend`

## Contexto
Rastreabilidade end-to-end.

## Critérios de aceite
- [ ] Middleware propaga X-Correlation-ID para gRPC, REST e logs

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): security headers (HSTS, nosniff, X-Frame-Options, CORS)`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `backend`

## Contexto
Hardening das respostas HTTP.

## Critérios de aceite
- [ ] HSTS, X-Content-Type-Options, X-Frame-Options e CORS restrito

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-004](PRD_PLATAFORMA_IOT.md)

#### `docs(backend): OpenAPI 3.0 published at /docs`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `docs`

## Contexto
Documentação pública da API.

## Critérios de aceite
- [ ] Swagger UI acessível publicamente

## Stack afetado
docs

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — MVP §12](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): deploy.sh / GitHub Actions automated deploy`
- **Assignee:** IncludeLuisFerreira · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `devops`

## Contexto
Deploy automatizado.

## Critérios de aceite
- [ ] build → push ECR → restart

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 2](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-002](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): rules engine Prometheus metrics`
- **Assignee:** deny759 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `backend`

## Contexto
Métricas do motor de regras.

## Critérios de aceite
- [ ] rules_evaluated_total, rule_latency_seconds, alerts_triggered_total

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(devops): MQTT broker monitoring`
- **Assignee:** deny759 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `devops`

## Contexto
Monitoramento do broker.

## Critérios de aceite
- [ ] Conexões ativas, messages_received e messages_sent

## Stack afetado
devops

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-006](PRD_PLATAFORMA_IOT.md)

#### `feat(backend): load test (10k messages, latency <= 2s)`
- **Assignee:** deny759 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `backend`

## Contexto
Validação da latência ponta-a-ponta.

## Critérios de aceite
- [ ] 10.000 mensagens MQTT
- [ ] Latência média <= 2s, zero perdas

## Stack afetado
backend

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-003](PRD_PLATAFORMA_IOT.md)

#### `docs(backend): ARCHITECTURE.md`
- **Assignee:** deny759 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `docs`

## Contexto
Diagrama final do sistema.

## Critérios de aceite
- [ ] docs/ARCHITECTURE.md com diagrama

## Stack afetado
docs

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — MVP §12](PRD_PLATAFORMA_IOT.md)

#### `docs(backend): DR.md (failover/disaster recovery)`
- **Assignee:** deny759 · **Milestone:** Sprint 8 · **Labels:** `sprint-8`, `docs`

## Contexto
Procedimento de recuperação de desastres.

## Critérios de aceite
- [ ] docs/DR.md com failover e recuperação

## Stack afetado
docs

## Referências
- [SPRINTS_BACKLOG.md — Sprint 8 · Aluno 3](SPRINTS_BACKLOG.md)
- [PRD_PLATAFORMA_IOT.md — RNF-002](PRD_PLATAFORMA_IOT.md)

---

**Total de issues:** 128
