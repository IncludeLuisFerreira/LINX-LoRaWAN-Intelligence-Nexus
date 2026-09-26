# README com `curl` (criar tenant + ingestar telemetria) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Documentar, com `curl`, os dois fluxos da S2 (criar tenant no SaaS REST e ingestar telemetria pelo Client Agent) no README do módulo e no espelho do MkDocs.

**Architecture:** Tarefa puramente documental. Adiciona-se uma seção ao `client_agent_api/README.md` e replica-se o arquivo em `docs/client_agent_api/README.md` (cópia consumida pelo MkDocs). A verificação é o `mkdocs build --strict` + conferência das rotas/schemas reais.

**Tech Stack:** Markdown, MkDocs (material).

---

## File Structure

- `client_agent_api/README.md` — fonte da documentação; recebe a nova seção.
- `docs/client_agent_api/README.md` — espelho do MkDocs; deve ficar idêntico à fonte.
- `PROGRESS.md` — marca a #39 como concluída.

---

### Task 1: Adicionar a seção "Fluxo ponta-a-ponta com `curl`" ao README do módulo

**Files:**
- Modify: `client_agent_api/README.md` (inserir após a seção `## 📍 Endpoints`, antes de `## 📁 Estrutura`)

- [ ] **Step 1: Inserir a seção**

Inserir o bloco abaixo imediatamente após a tabela de `## 📍 Endpoints` (nota: o texto usa `curl` com hosts genéricos `<saas>` e `<agent>`):

````markdown
## 🌐 Fluxo ponta-a-ponta com `curl`

Dois fluxos demonstram a Sprint 2: **criar um tenant** no SaaS REST e **ingestar
telemetria** pelo Client Agent. Os comandos valem para local e AWS — troque apenas
o host.

### Pré-requisitos e portas

| Serviço        | Porta   | Papel no fluxo                                           |
| -------------- | ------- | -------------------------------------------------------- |
| `identity_api` | `8000`  | SaaS REST — cria o tenant.                               |
| `client_agent` | `8001`  | Middleware — recebe a telemetria em `/ingest`.           |
| `tenant_app`   | `8002`  | Ambiente isolado — persiste a telemetria no TimescaleDB. |
| `agent_bridge` | `50051` | gRPC do SaaS — configuração do tenant (`GetAppConfig`).  |

Suba a stack e confirme que os serviços estão de pé:

```bash
cd deploy
docker compose up -d --build
docker compose ps          # identity_api, client_agent, tenant_app e agent_bridge "Up"
```

> A ingestão só responde `201` com o `tenant_app` no ar e o gRPC do SaaS
> (`agent_bridge`) resolvível; caso contrário, veja Erros comuns.

### 1. Criar um tenant no SaaS (`identity_api`)

```bash
curl -i -X POST http://<saas>:8000/api/v1/tenant/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "ACME"}'
```

Resposta esperada (`201 Created`), com o `id` em UUID v4 e o header `Location`
apontando para o recurso:

```http
HTTP/1.1 201 Created
location: http://<saas>:8000/api/v1/tenant/3f1b6d3a-6c2e-4a1f-9c8b-2f0d5a7e1b44
content-type: application/json

{
  "name": "ACME",
  "description": "",
  "id": "3f1b6d3a-6c2e-4a1f-9c8b-2f0d5a7e1b44",
  "created_at": "2026-09-26T12:00:00Z",
  "updated_at": "2026-09-26T12:00:00Z"
}
```

> O `POST` exige a **barra final** (`/api/v1/tenant/`). Sem ela o FastAPI responde
> `307 Temporary Redirect`.

### 2. Ingestar telemetria no Client Agent

```bash
curl -i -X POST http://<agent>:8001/ingest \
  -H 'Content-Type: application/json' \
  -d '{"dev_eui": "dev1", "payload": {"temperature": 25.5}, "rssi": -50, "snr": 9.5}'
```

Resposta esperada (`201 Created`):

```http
HTTP/1.1 201 Created
content-type: application/json

{"ok": true}
```

O middleware valida o schema e encaminha para o `POST /ingest` do `tenant_app`
(`TENANT_APP_URL`, default `http://localhost:8002`), que grava na hypertable
`telemetry` do TimescaleDB. `rssi` e `snr` são opcionais.

### Reproduzindo na AWS

Os comandos são os mesmos; mude apenas o host:

- `<saas>` e `<agent>` → IP público ou DNS das instâncias EC2 (podem ser a mesma
  máquina, com portas distintas).
- **Security Group (inbound):** libere `8000` (REST) e `8001` (ingest). A porta
  `50051` (gRPC) **não** deve ir para `0.0.0.0/0` — restrinja ao IP do Client Agent.
- Com a borda TLS em nginx (#181), use `https://<dominio>` no lugar de
  `http://<saas>`; o encaminhamento interno para o backend permanece em HTTP.

### Erros comuns

| Resposta                   | Causa provável                                                              |
| -------------------------- | -------------------------------------------------------------------------- |
| `307` em `/api/v1/tenant`  | Falta a barra final (`/api/v1/tenant/`).                                   |
| `422 Unprocessable Entity` | Payload fora do schema (`name` ausente, tipos errados, `dev_eui` vazio).   |
| `502 Bad Gateway`          | `tenant_app` inacessível ao `client_agent` (`TENANT_APP_URL`).             |
| `503 Service Unavailable`  | gRPC do SaaS inacessível ou pool do TimescaleDB indisponível.              |
| `404 Not Found`            | `tenant_id`/`app_id` inexistente em rotas com `{id}`.                      |

> Visão completa da topologia, contrato gRPC e variáveis de ambiente:
> [Comunicação entre Serviços](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/blob/develop/docs/comunicacao_entre_servicos.md).
````

- [ ] **Step 2: Conferir as rotas/schemas documentados**

Run: `grep -n "prefix" saas_backend/identity_api/src/identity_api/routes/tenant.py client_agent_api/src/agent/routers/ingest.py`
Expected: prefix `/api/v1/tenant` e rota `"/ingest"` — batem com o texto.

- [ ] **Step 3: Commit**

```bash
git add client_agent_api/README.md
git commit -m "docs(#39): README com curl para criar tenant e ingestar telemetria"
```

---

### Task 2: Espelhar no README do MkDocs

**Files:**
- Modify: `docs/client_agent_api/README.md`

- [ ] **Step 1: Copiar a fonte para o espelho**

Run:

```bash
cp client_agent_api/README.md docs/client_agent_api/README.md
```

- [ ] **Step 2: Confirmar que ficaram idênticos**

Run: `diff -u client_agent_api/README.md docs/client_agent_api/README.md`
Expected: sem saída (arquivos idênticos).

- [ ] **Step 3: Commit**

```bash
git add docs/client_agent_api/README.md
git commit -m "docs(#39): espelha o README do client_agent no MkDocs"
```

---

### Task 3: Marcar a #39 como concluída no PROGRESS.md

**Files:**
- Modify: `PROGRESS.md:48`

- [ ] **Step 1: Atualizar o checklist**

Trocar:

```markdown
- [ ] [#39 docs(backend): README with curl for create tenant + ingest telemetry](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/39)
```

por:

```markdown
- [x] [#39 docs(backend): README with curl for create tenant + ingest telemetry](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/39)
```

- [ ] **Step 2: Commit**

```bash
git add PROGRESS.md
git commit -m "docs(#39): marca a issue como concluída no PROGRESS"
```

---

### Task 4: Validar o build do MkDocs

**Files:**
- Nenhum (verificação)

- [ ] **Step 1: Rodar o build estrito**

Run: `poetry run mkdocs build --strict`
Expected: `INFO - Documentation built in ...` sem warnings/erros. Se o Poetry não
estiver instalado, instalar as deps da raiz antes (`poetry install`).

- [ ] **Step 2: Conferir o resultado no site gerado (opcional)**

Run: `grep -c "Fluxo ponta-a-ponta com" site/client_agent_api/index.html`
Expected: `1`.

---

### Task 5: Abrir a PR

**Files:**
- Nenhum (operação de git/GitHub)

- [ ] **Step 1: Push da branch**

```bash
git push -u origin issue39_readme_curl
```

- [ ] **Step 2: Criar a PR para `develop` descrevendo os critérios da #39**

```bash
gh pr create --base develop --title "docs(client-agent): README com curl para criar tenant + ingestar telemetria (#39)" --body "$(cat <<'EOF'
## O que

Documenta no `client_agent_api/README.md` (e no espelho `docs/client_agent_api/README.md`)
os dois fluxos ponta-a-ponta da S2 com `curl`:

1. Criar tenant via SaaS REST (`POST /api/v1/tenant/`) — resposta `201`.
2. Ingestar telemetria via Client Agent (`POST /ingest`) — resposta `201 {"ok": true}`.

Inclui pré-requisitos/portas, como reproduzir na AWS e uma tabela de erros comuns.

## Critérios da #39

- [x] README documenta os dois fluxos com `curl`
- [x] Comandos reproduzíveis em ambiente AWS
- [x] Respostas esperadas incluídas

Closes #39
EOF
)"
```

Expected: URL da PR impressa. **Não** fazer merge sem autorização.
