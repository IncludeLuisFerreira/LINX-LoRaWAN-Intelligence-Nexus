# Design: README com `curl` para criar tenant + ingestar telemetria (issue #39)

**Data:** 2026-09-26
**Issue:** [#39](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/39)
**Sprint:** 2
**Escopo:** documentar, com `curl`, os dois fluxos ponta-a-ponta da S2 — criar tenant via SaaS REST (`identity_api`) e ingestar telemetria via Client Agent (`client_agent_api`) — incluindo portas, pré-requisitos, respostas esperadas e execução na AWS.
**Relacionado:** #36 (pipeline de ingestão), #38 (prova gRPC no `tenant_app`), `#181` (nginx/TLS na borda), `docs/comunicacao_entre_servicos.md` (visão de comunicação entre serviços).

## Contexto

A issue #39 pede um README com exemplos `curl` dos dois fluxos da S2, tornando a
sprint demonstrável e reprodutível. Já existe uma seção "Como verificar" em
`docs/comunicacao_entre_servicos.md` (§8) com os dois `curl`, mas ela é uma visão
de comunicação entre serviços, sem respostas esperadas completas nem passos de AWS,
e não está no README do módulo exigido pela issue.

## Objetivo

Adicionar uma seção "Fluxo ponta-a-ponta com `curl`" ao `client_agent_api/README.md`
documentando:

1. Pré-requisitos e portas dos serviços envolvidos.
2. Criação de tenant via SaaS REST, com resposta esperada (`201` + corpo).
3. Ingestão de telemetria via Client Agent, com resposta esperada (`201 {"ok": true}`).
4. Como reproduzir na AWS (hosts, Security Group, TLS).
5. Erros comuns e o que significam.

## Não-objetivos

- Alterar código, rotas ou testes.
- Documentar endpoints ainda inexistentes (ex.: `GET /telemetry`, que é da S3).
- Substituir ou duplicar `docs/comunicacao_entre_servicos.md`; a seção nova linkará
  esse documento para a visão completa da topologia.

## Onde

- `client_agent_api/README.md` — README do módulo (fonte, exigido pela issue).
- `docs/client_agent_api/README.md` — cópia mantida manualmente e consumida pelo
  MkDocs (`mkdocs.yml`, nav "Client Agent API"). Precisa ser atualizada em espelho
  para o `mkdocs build --strict` e o site não divergirem.

## Estrutura da seção

Título: `## 🌐 Fluxo ponta-a-ponta com curl`.

1. **Pré-requisitos e portas** — tabela com `identity_api :8000`, `client_agent :8001`,
   `tenant_app :8002`, `agent_bridge :50051`; subir a stack com
   `cd deploy && docker compose up -d --build` e conferir com `docker compose ps`.
   Nota: a ingestão exige `tenant_app` no ar e o gRPC do SaaS resolvível.

2. **Passo 1 — criar tenant no SaaS (`identity_api`)**

   ```bash
   curl -i -X POST http://<saas>:8000/api/v1/tenant/ \
     -H 'Content-Type: application/json' \
     -d '{"name": "ACME"}'
   ```

   Resposta esperada `201 Created`, header `Location`, corpo com `id` (UUID v4),
   `name`, `description`, `created_at`, `updated_at`.

3. **Passo 2 — ingestar telemetria no Client Agent**

   ```bash
   curl -i -X POST http://<agent>:8001/ingest \
     -H 'Content-Type: application/json' \
     -d '{"dev_eui": "dev1", "payload": {"temperature": 25.5}, "rssi": -50, "snr": 9.5}'
   ```

   Resposta esperada `201 {"ok": true}`. Explicar o caminho: o middleware valida e
   encaminha para o `POST /ingest` do `tenant_app` (`:8002`), que persiste na
   hypertable do TimescaleDB.

4. **AWS** — `<saas>`/`<agent>` são o IP público/DNS das EC2; liberar `8000` (REST) e
   `8001` (ingest) no Security Group e restringir `50051` ao IP do Client Agent
   (atenção P0 do `saas_backend/README.md`). Se houver nginx/TLS na borda (`#181`),
   trocar `http://` por `https://` e usar o domínio. Os comandos são idênticos,
   mudando só o host.

5. **Erros comuns** — tabela: `307` (barra final ausente em `/api/v1/tenant/`),
   `422` (payload inválido), `502`/`503` (`tenant_app`/gRPC inacessível), `404`
   (tenant inexistente em rotas com `{id}`).

## Verificação

- `poetry run mkdocs build --strict` na raiz (garante o espelho e o nav).
- Conferir que os comandos batem com as rotas reais (`identity_api/routes/tenant.py`,
  `client_agent_api/src/agent/routers/ingest.py`, `tenant_app_template/src/tenant/routers/ingest.py`)
  e com os schemas (`TenantResponse`).
- Smoke opcional: subir a stack (`deploy/docker-compose.yml`) e executar os dois
  `curl`, confirmando `201` e corpos documentados.

## Decisões e riscos

- **Espelho manual:** `docs/client_agent_api/README.md` é cópia (não symlink) por
  decisão da #177; mantê-la em sincronia é responsabilidade desta PR.
- **Sem `description` no exemplo:** o `TenantCreate` tem `description` opcional
  (default `""`); mantemos o exemplo mínimo da issue e citamos o campo na resposta.
- **Risco:** respostas esperadas foram derivadas do código/schemas, não capturadas
  de uma execução real na AWS. Se o smoke local for viável, alinhamos o texto ao
  output real.
