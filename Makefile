# O .PHONY avisa ao Make que essas palavras são nomes de comandos, e não nomes de arquivos físicos na pasta.
.PHONY: help up down logs build stop-all progress integration test-integration \
	up-infra down-infra logs-infra \
	up-base down-base logs-base \
	up-core down-core logs-core \
	up-client down-client logs-client \
	up-deploy down-deploy logs-deploy \
	up-client-agent down-client-agent logs-client-agent \
	build-tenant-image

# Composes do repositório. O `up`/`down`/`logs`/`build` sem sufixo operam a
# stack de infraestrutura (retrocompatível com o quickstart do README).
INFRA         := infra/docker-compose.yml
INFRA_BASE    := infra/docker-compose.base.yml
CORE          := linx_core/docker-compose.yml
CLIENT        := client/docker-compose.yml
DEPLOY        := deploy/docker-compose.yml
CLIENT_AGENT  := deploy/docker-compose.client-agent.yml

help:
	@echo "Targets por stack do monorepo:"
	@echo "  up-infra        $(INFRA)"
	@echo "  up-base         $(INFRA_BASE)"
	@echo "  up-core         $(CORE)"
	@echo "  up-client       $(CLIENT)"
	@echo "  up-deploy       $(DEPLOY)"
	@echo "  up-client-agent $(CLIENT_AGENT)"
	@echo "  build-tenant-image  imagem mínima linx-tenant-app:latest"
	@echo "  test-integration  tests/integration/run.sh"
	@echo "Cada stack tem também down-<stack> e logs-<stack>."

# --- Infraestrutura base (ChirpStack v4 + MQTT + PostgreSQL) ---
# `up`/`build`/`down`/`logs` mantêm o comportamento histórico (stack `infra/`).
up: stop-all
	bash deploy/scripts/bootstrap-network.sh
	docker compose -f $(INFRA) up -d

build:
	bash deploy/scripts/bootstrap-network.sh
	docker compose -f $(INFRA) up -d --build

down:
	docker compose -f $(INFRA) down

logs:
	docker compose -f $(INFRA) logs -f

up-infra:
	bash deploy/scripts/bootstrap-network.sh
	docker compose -f $(INFRA) up -d
down-infra:
	docker compose -f $(INFRA) down
logs-infra:
	docker compose -f $(INFRA) logs -f

# --- Base de dev (PostgreSQL 15 + Redis 7 + Mosquitto) ---
up-base:
	docker compose -f $(INFRA_BASE) up -d
down-base:
	docker compose -f $(INFRA_BASE) down
logs-base:
	docker compose -f $(INFRA_BASE) logs -f

# --- Imagem mínima provisionada por aplicação (issue #58) ---
build-tenant-image:
	docker build -t linx-tenant-app:latest client/tenant_app

# --- Plano de controle (linx_core: identity_api + agent_bridge + db) ---
up-core:
	docker compose -f $(CORE) up -d
down-core:
	docker compose -f $(CORE) down
logs-core:
	docker compose -f $(CORE) logs -f

# --- Ambiente isolado do cliente (frontend + telemetry_consumer + TimescaleDB) ---
up-client:
	docker compose -f $(CLIENT) up -d
down-client:
	docker compose -f $(CLIENT) down
logs-client:
	docker compose -f $(CLIENT) logs -f

# --- Stack full-stack de produção (nginx + TLS + todos os serviços) ---
# Garante a rede compartilhada com o stack infra antes de subir o routing.
up-deploy:
	bash deploy/scripts/bootstrap-network.sh
	docker compose -f $(DEPLOY) up -d
down-deploy:
	docker compose -f $(DEPLOY) down
logs-deploy:
	docker compose -f $(DEPLOY) logs -f

# --- Client Agent isolado (compose dedicado em deploy/) ---
up-client-agent:
	docker compose -f $(CLIENT_AGENT) up -d
down-client-agent:
	docker compose -f $(CLIENT_AGENT) down
logs-client-agent:
	docker compose -f $(CLIENT_AGENT) logs -f

# COMANDO PARA PARAR TUDO (IGNORA SE NÃO HOUVER CONTAINERS RODANDO)
stop-all:
	docker ps -q | xargs -r docker stop

# Atualiza o PROGRESS.MD com o estado atual das issues.
progress:
	python3 scripts/update_progress.py

# Testes de integração ponta-a-ponta (sobe a stack de tests/integration,
# roda o pytest e derruba tudo no fim).
integration test-integration:
	tests/integration/run.sh
