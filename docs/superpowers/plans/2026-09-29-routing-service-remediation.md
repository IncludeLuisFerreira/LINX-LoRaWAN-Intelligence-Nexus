# Routing Service (#47) — Remediação do Code Review

> **For agentic workers:** Use superpowers:subagent-driven-development.

**Goal:** Corrigir os bloqueantes e avisos do review da PR #185 (routing service: uplink MQTT → device_routes → client agent), deixando `pytest` verde e o deploy subindo em host limpo.

**Branch de trabalho:** `issue47_routing_service` (já ativa).

**Contexto da issue #47 (critérios de aceite):**
- Uplink MQTT roteado via `device_routes` para o `agent_endpoint` correto.
- `dev_eui` sem rota logado e descartado (não crasha).
- Telemetria de dois tenants vai para endpoints distintos.

## Global Constraints

- **NÃO fazer `git commit` e NÃO fazer `git push`.** Deixar as mudanças na working tree.
- Python 3.12; `black` line-length 79; `isort` profile black (line_length 79); `flake8`; `mypy`.
- Testes rodam com: `cd saas_backend/routing && poetry run pytest -q` (ou `poetry run task test`). Saída deve ser limpa (sem warnings/ruído).
- Comandos de lint: `poetry run task lint-check`, `poetry run task mypy`, `poetry run task flake8`.
- Manter o estilo de logs em pt-BR já existente; não adicionar comentários supérfluos.
- Só tocar nos arquivos listados em cada task.

---

## Task 1: Corrigir worker/queue e os testes quebrados (BLOQUEANTE)

**Files:**
- Modify: `saas_backend/routing/src/routing/routing.py`
- Modify: `saas_backend/routing/tests/test_routing.py`

**Problema:** `on_message` passou a apenas enfileirar em `_q` (Worker pool), mas `test_on_message_routes_uplink` ainda espera chamada direta a `route_uplink` → 1 teste falha. Os testes `test_on_message_invalid_json_does_not_route` e `test_on_message_invalid_topic_does_not_route` passam vazios (assertam que não chama, quando na verdade nunca chama naquele caminho).

**Requisitos:**
1. `route_uplink` continua sendo a unidade de roteamento (sem mudança de assinatura).
2. `on_message` continua apenas enfileirando em `_q` (não bloquear a thread do paho).
3. Tornar `_q` atributo de instância (`self._q`) e usar `self.num_workers` no loop de `start()`; remover a constante global `NUM_OF_WORKERS` **ou** usá-la apenas como default de `num_workers` no `__init__`. `start()` deve usar `self.num_workers`.
4. Extrair o processamento de uma mensagem da fila para um método testável `_handle_uplink(topic, payload)` (já existe) — os testes devem chamar `_handle_uplink` (ou drenar `self._q`) para verificar o roteamento.
5. Reescrever os testes de `on_message` para verificar comportamento real:
   - `test_on_message_routes_uplink` → enfileira e depois processa via `router._handle_uplink(...)`, assertando que `route_uplink` foi chamado com `dev_eui`, payload e `http_client`.
   - `test_on_message_invalid_json_does_not_route` → chamar `_handle_uplink` com payload inválido, assertando que `route_uplink` **não** foi chamado.
   - `test_on_message_invalid_topic_does_not_route` → idem com tópico inválido.
   - Adicionar teste de que `on_message` coloca um item em `router._q` (prova que não roteia direto e não bloqueia).
6. `poetry run pytest -q` deve passar 100% sem warnings.

**Verificação:** `cd saas_backend/routing && poetry run pytest -q` (esperado: all passed) e `poetry run task lint-check`.

**Report:** `DONE` + commits (nenhum, mudanças na working tree) + resumo dos testes.

---

## Task 2: Endurecer entrada (dev_eui case-insensitive + validação de agent_endpoint)

**Files:**
- Modify: `saas_backend/routing/src/routing/routing.py`
- Modify: `saas_backend/routing/tests/test_routing.py`

**Problemas:**
- `dev_eui` do tópico é comparado de forma case-sensitive com a coluna `device_routes.dev_eui`; EUIs hex podem diferir em caixa.
- `agent_endpoint` vindo do DB é usado direto em `client.post(url, ...)`, sem validar esquema → vetor de SSRF/erro.

**Requisitos:**
1. Busca por `dev_eui` case-insensitive: usar `func.lower(DeviceRoute.dev_eui) == dev_eui.lower()` (ou normalizar `dev_eui` de forma consistente). Manter o valor original no log.
2. Validar o `agent_endpoint` antes do POST: aceitar somente esquema `http` ou `https` (usar `urllib.parse.urlsplit`). Se inválido, logar `warning`/`error` e retornar `False` sem POST.
3. Testes novos:
   - `dev_eui` com case diferente do armazenado continua roteando (session factory mockada recebe a query; garantir que `.lower()` aparece no filtro — pode ser verificado com o mock de sessão).
   - `agent_endpoint` com esquema `file://` ou `ftp://` retorna `False` e não faz POST.
   - `agent_endpoint` http/https continua roteando (não quebrar o caminho feliz).
4. `poetry run pytest -q` verde e `poetry run task lint-check`.

**Report:** `DONE` + resumo dos testes.

---

## Task 3: Teste de aceite — dois tenants, endpoints distintos

**Files:**
- Modify: `saas_backend/routing/tests/test_routing.py`

**Problema:** critério de aceite "Telemetria de dois tenants vai para endpoints distintos" não tem teste.

**Requisitos:**
1. Adicionar `test_route_uplink_two_dev_euis_go_to_distinct_endpoints`:
   - Duas session factories mockadas retornando rotas com `agent_endpoint` distintos.
   - Chamar `route_uplink` para dois `dev_eui` diferentes.
   - Asserts: cada `http.post` chamado com o endpoint correspondente e o caminho `/ingest`.
2. Não usar SQLite real (o `DeviceRoute` usa `UUID` do dialeto postgresql); usar mocks de sessão.
3. `poetry run pytest -q` verde.

**Report:** `DONE` + resumo dos testes.

---

## Task 4: Bootstrap da rede `linx-network` + corrigir docs stale (BLOQUEANTE de deploy)

**Files:**
- Modify: `saas_backend/docker-compose.yml` (comentário na definição do serviço `routing`)
- Modify: `infra/docker-compose.yml` (garantir bootstrap/erro claro)
- Modify: `README.md` (documentar criação da rede externa)
- Create: `deploy/scripts/bootstrap-network.sh`

**Problemas:**
- `linx-network` é `external: true` em `infra/docker-compose.yml` e `saas_backend/docker-compose.yml`, mas nenhum compose a cria e não há instrução documentada → `docker compose up` falha em host limpo.
- Comentário em `saas_backend/docker-compose.yml` ainda diz `docker network create linx-infra` (nome antigo).

**Requisitos:**
1. Criar `deploy/scripts/bootstrap-network.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   NETWORK="${1:-linx-network}"
   docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"
   echo "network ${NETWORK} pronta"
   ```
   com `chmod +x`.
2. Documentar no `README.md` (seção de subir serviços): rodar `./deploy/scripts/bootstrap-network.sh` antes de `docker compose up` no deploy agregado; mencionar que `linx-network` deve existir para os serviços do perfil `iot`.
3. Corrigir o comentário stale `linx-infra` → `linx-network` em `saas_backend/docker-compose.yml` (linha ~76).
4. Validar sintaxe dos composes: `docker compose -f deploy/docker-compose.yml config` (se Docker disponível; se não, usar `docker compose ... config` e reportar). Não alterar nomes de rede.
5. NÃO renomear a rede de volta; manter `linx-network`.

**Report:** `DONE` + saída de validação dos composes.

---

## Task 5: Higiene (batching de ajustes pequenos)

**Files:**
- Modify: `saas_backend/routing/src/routing/routing.py`
- Modify: `infra/docker-compose.yml`
- Modify: `saas_backend/docker-compose.yml`
- Modify: `saas_backend/routing/tests/test_routing.py`

**Requisitos (batch):**
1. Garantir newline no fim de `routing.py`, `infra/docker-compose.yml` e `saas_backend/docker-compose.yml`.
2. Em `test_routing.py`, `_router_with_mock_client()` cria `httpx.Client` real nunca fechado → fechar/injetar mock (`router.http_client = MagicMock()` e fechar no teardown ou substituir por mock). Evitar `ResourceWarning`.
3. Rodar `poetry run pytest -q` (deve ficar sem warnings).

**Report:** `DONE` + resumo.

---

## Deferido (não fazer agora, anotar no ledger)

- Métrica/observabilidade de descarte por fila cheia (QoS 0) e persistência — requer decisão de arquitetura.
- Autenticação/TLS no broker MQTT (`allow_anonymous true`) — mudança de infra, fora do escopo da PR.
- Allowlist de hosts para `agent_endpoint` (SSRF completo) — requer config nova.
