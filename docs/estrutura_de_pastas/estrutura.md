# Estrutura de Pastas - Projeto LINX (Cloud)

Este documento resume a estrutura de primeiro nível do repositório do projeto
LINX e o objetivo de cada diretório.

| Diretório / Pasta | Objetivo Principal |
| :--- | :--- |
| **`linx_core/`** | Plano de controle (Core) da plataforma. Microsserviços `services/identity_api/` (REST FastAPI, dono da autenticação/validação de credenciais do plano de controle) e `services/agent_bridge/` (gRPC AgentBridge), além da biblioteca comum `shared/` (`linx_shared`, incluindo os stubs gRPC do contrato). Integra com ChirpStack/MQTT e orquestra o provisionamento dos tenants. |
| **`middleware/`** | Camada de middleware. `services/routing/` roteia os uplinks MQTT do ChirpStack para a exchange RabbitMQ do tenant. `services/client_agent/` é o agente por tenant (endpoint `/health` e cliente gRPC ao Linx Core). O `client_agent` **não** valida JWT nem faz roteamento de requisições — essa responsabilidade é do `identity_api` (`linx_core/`). |
| **`client/`** | Ambiente isolado do cliente. Contém o dashboard web (`frontend/`), o consumidor de telemetria (`services/telemetry_consumer/`) e a estrutura do banco de dados (`db/`, TimescaleDB). Quando uma nova aplicação é criada, este diretório dita como o contêiner daquele cliente deve ser construído na nuvem. |
| **`client/frontend/`** | Aplicação web (Dashboard/Interface) do cliente. Renderiza os painéis consumindo o plano de controle via REST (`/api`) e a telemetria via REST/WebSocket, dependendo da aplicação acessada. O nginx do container injeta o token de serviço nos proxies `/api` e `/ws`. |
| **`client/services/telemetry_consumer/`** | Serviço por tenant: consome a fila `linx.telemetry.{app_id}` (AMQP) e grava no TimescaleDB; expõe histórico (`GET /telemetry`) e stream (`WS /ws/telemetry/{app_id}`), ambos exigindo o token de serviço. |
| **`infra/`** | Orquestração da **infraestrutura base** compartilhada. Arquivos Docker Compose e configurações dos serviços de sustentação da nuvem, como o ChirpStack (LoRaWAN Network Server), o broker MQTT e o banco de dados SaaS principal. |
| **`deploy/`** | Stack full-stack de produção (`docker-compose.yml` com nginx + TLS e todos os serviços), Compose dedicado do `client_agent`, certificados e exemplos de ambiente. O schema do TimescaleDB fica em `client/db/schema.sql`. |
| **`proto/`** | Contrato gRPC compartilhado (`linx_agent.proto`, serviço `AgentBridge`). Fonte única para geração dos stubs em `linx_core/shared`. |
| **`scripts/`** | Utilitários de operação: geração de stubs gRPC (`gen_proto.sh`), atualização de progresso (`update_progress.py`) e instalação de Docker (`docker_install.sh`). |
| **`tests/`** | Testes de integração ponta-a-ponta (`tests/integration/`), que sobem a stack real via `deploy/docker-compose.yml`. |
| **`docs/`** | Documentação do projeto (MkDocs Material), publicada como site. |
| **`website/`** | Site institucional (Astro). |
| **`.github/`** | Workflows de CI/CD (`backend-ci`, `frontend-ci`, `middleware-ci`, `telemetry-consumer-ci`, `integration-ci`, `docs-ci`, `website-ci`). |
