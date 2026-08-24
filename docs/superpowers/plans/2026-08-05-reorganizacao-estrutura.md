# Reorganização da Estrutura do Repositório Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar as pastas do repositório `IncludeLuisFerreira/Servidor-LoRaWAN` em domínios funcionais (`platform/`, `infrastructure/`, `firmware/`), renomeando pastas, sketches Arduino e nomes de pacotes npm, e atualizando todas as referências (README, plano ativo, issues #1–14).

**Architecture:** Movimentação de pastas inteiras via `mv` do sistema (preserva `node_modules/`, `venv/`, `dist/` não rastreados), renomeações pontuais de sketches e package.json, e atualização de referências de caminho em docs e issues do GitHub. Commit único descritivo ao final. Nenhum código de aplicação é alterado (apenas caminhos e nomes).

**Tech Stack:** bash/mv, git, `gh` CLI (GitHub), edição de arquivos MD/JSON/py. Sem TDD aplicável — verificação é estrutural (`git status`, `git ls-files`, typecheck/testes preservados).

**Spec:** `docs/superpowers/specs/2026-08-05-reorganizacao-estrutura-design.md`

---

## Decisões a respeitar

1. Usar `mv` do sistema (não `git mv`) para mover pastas inteiras — preserva diretórios não rastreados (`node_modules/`, `venv/`, `dist/`, `__pycache__/`).
2. Sketches Arduino renomeados para casar com o nome da pasta (exigência do Arduino IDE): `end-device.ino` e `gateway.ino`.
3. Nomes de pacotes npm renomeados: `platform-backend`, `platform-frontend`.
4. Docs históricos 2026-07-30 **não** são alterados (registro de trabalho concluído).
5. PRD não tem referências de caminho — inalterado.
6. Ao final, `npm test` e `npm run typecheck` em `platform/backend` devem continuar verde (prova de que nada quebrou).

---

## File Structure (antes → depois)

```
Antes                                Depois
chirpstack-dashboard/              → platform/
  backend/                           platform/backend/
  frontend/                          platform/frontend/
chirpstack-docker/                 → infrastructure/
  app/                               infrastructure/app/
  configuration/                     infrastructure/configuration/
ESP-End-Device-LORAWAN-ABP-        → firmware/end-device/
  ESP32-RFM95-LDR/
ESP_sc_gway_pk/                    → firmware/gateway/
docs/                              → docs/ (inalterado)
PRD_PLATAFORMA_IOT.md              → raiz (inalterado)
```

---

## Task 1: Mover pastas e renomear sketches

**Files:**
- Move: `chirpstack-dashboard/` → `platform/`
- Move: `chirpstack-docker/` → `infrastructure/`
- Move: `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR/` → `firmware/end-device/`
- Move: `ESP_sc_gway_pk/` → `firmware/gateway/`
- Rename: `firmware/end-device/ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR.ino` → `firmware/end-device/end-device.ino`
- Rename: `firmware/gateway/ESP_sc_gway_pk.ino` → `firmware/gateway/gateway.ino`

- [ ] **Step 1: Mover as quatro pastas de topo**

Run (from repo root):

```bash
mv chirpstack-dashboard platform
mv chirpstack-docker infrastructure
mkdir -p firmware
mv ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR firmware/end-device
mv ESP_sc_gway_pk firmware/gateway
```

Expected: `ls` na raiz mostra `platform/`, `infrastructure/`, `firmware/`, `docs/`, `PRD_PLATAFORMA_IOT.md`, `README.md`.

- [ ] **Step 2: Renomear os sketches principais do Arduino**

Run (from repo root):

```bash
mv firmware/end-device/ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR.ino firmware/end-device/end-device.ino
mv firmware/gateway/ESP_sc_gway_pk.ino firmware/gateway/gateway.ino
```

Expected: `ls firmware/end-device/` contém `end-device.ino` (sem o nome antigo); `ls firmware/gateway/` contém `gateway.ino`.

- [ ] **Step 3: Renomear os nomes dos pacotes npm**

Modify `platform/backend/package.json`, campo `name`:

```json
"name": "platform-backend",
```

Modify `platform/frontend/package.json`, campo `name`:

```json
"name": "platform-frontend",
```

- [ ] **Step 4: Verificar estrutura movida**

Run:

```bash
git status --short
```

Expected: renames detectados (`R  chirpstack-dashboard → platform`, etc.) — o git pode mostrar como delete+add até o commit, o que é esperado. `node_modules/`, `venv/`, `dist/` não aparecem (ignorados).

- [ ] **Step 5: Verificar que testes/typecheck continuam verde (ainda sem commit)**

Run (from `platform/backend`):

```bash
npm run typecheck && npm test
```

Expected: typecheck OK e suíte Vitest verde (nenhum import relativo quebrou porque `backend/src` não foi reorganizado).

---

## Task 2: Atualizar README raiz

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Atualizar referências de pastas**

Em `README.md`, substituir todas as ocorrências de caminho de pasta:

| De | Para |
|----|------|
| `chirpstack-dashboard/` | `platform/` |
| `chirpstack-docker/` | `infrastructure/` |
| `ESP_sc_gway_pk.ino` | `gateway.ino` |
| `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR.ino` | `end-device.ino` |
| `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR/` | `firmware/end-device/` |
| `ESP_sc_gway_pk/` | `firmware/gateway/` |

Atenção: **não** substituir as ocorrências `chirpstack-docker` que são URL/importação (ex.: linha 44 `https://github.com/chirpstack/chirpstack-docker`, linha 47 `git clone https://github.com/chirpstack/chirpstack-docker.git`) — essas referem-se ao repositório upstream oficial e devem permanecer.

Ocorrências a atualizar (confirmadas por grep):
- Linha 17: link `[`chirpstack-dashboard/`](chirpstack-dashboard/README.md)` → `[`platform/`](platform/README.md)`
- Linha 48: `cd chirpstack-docker` → `cd infrastructure` (passo de reprodução)
- Linha 53: "Dentro de `chirpstack-docker/` foram criados..." → `infrastructure/`
- Linha 397: `Abra \`ESP_sc_gway_pk.ino\`` → `Abra \`gateway.ino\``
- Linha 446: "...criados dentro da pasta `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR/`:" → `firmware/end-device/`
- Linha 501: título `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR.ino` → `end-device.ino`
- Linha 772: `Abra \`ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR.ino\`` → `Abra \`end-device.ino\``
- Linha 811/817/826: `chirpstack-dashboard/` → `platform/`
- Linha 836: `cp ESP_sc_gway_pk/configNode.h ESP_sc_gway_pk/configNode.h.template` → `cp firmware/gateway/configNode.h firmware/gateway/configNode.h.template`

- [ ] **Step 2: Atualizar a seção "Estrutura"**

Substitua a árvore no final do `README.md` (linhas 850–916) pela nova estrutura:

```
LoraWan-project/
├── platform/                                 # SaaS multi-tenant (backend + frontend)
│   ├── docker-compose.yml                    # backend + postgres (TimescaleDB) + frontend (nginx)
│   ├── .env.example                          # todas as variáveis de ambiente
│   ├── backend/                              # Node.js/TypeScript (MQTT, REST, Socket.io, alertas)
│   │   └── src/
│   │       ├── index.ts                      # orquestração (HTTP + Socket.io + MQTT)
│   │       ├── mqtt/                         # cliente MQTT + parser v4
│   │       ├── db/                           # pool, migrate e init.sql (TimescaleDB)
│   │       ├── services/                     # persistência em batch, live, threshold engine
│   │       ├── alerts/                       # Telegram + E-mail
│   │       └── routes/                       # API REST
│   └── frontend/                             # React (Vite + Tailwind + Recharts)
│       └── src/
│           ├── api/                          # cliente REST
│           ├── socket/                       # Socket.io-client
│           └── components/                   # Cards, gráfico real-time, histórico, alertas
│
├── infrastructure/                           # Stack ChirpStack Docker (Network Server)
│   ├── docker-compose.yml                    # ChirpStack, gateway-bridge, REST API, DB, broker
│   ├── Makefile                              # importação de perfis de dispositivo
│   ├── app/                                  # webapp Flask de monitoramento
│   └── configuration/                        # chirpstack, gateway-bridge, mosquitto, postgresql
│
├── firmware/
│   ├── end-device/                           # Firmware do nó sensor (ESP32 + RFM95 + LDR)
│   │   ├── end-device.ino                    # Sketch principal
│   │   ├── config.h                          # Constantes (NVS, TX interval)
│   │   ├── lmic_project_config.h             # Configuração LMIC (SX1276, AU915)
│   │   ├── 1_PHY.ino ... 5_APP.ino           # Camadas PHY/MAC/NET/TRANSP/APP
│   └── gateway/                              # Firmware do gateway single-channel
│       ├── gateway.ino                       # Sketch principal
│       ├── configGway.h                      # Configuração de banda e recursos
│       ├── configNode.h                      # Credenciais WiFi e lista de nós
│       ├── loraModem.h                       # Definições do rádio e pinagens
│       └── _*.ino                            # Módulos (WiFi, Semtech UDP, web, OTA, ...)
│
├── docs/                                     # Manuais, análise de segurança, specs/plans
├── PRD_PLATAFORMA_IOT.md                     # Requisitos do produto (Fase A)
└── README.md
```

- [ ] **Step 3: Verificar**

Run:

```bash
grep -n "chirpstack-dashboard\|ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR\|ESP_sc_gway_pk" README.md
```

Expected: sem resultados (ou apenas referências intencionais a URLs upstream `chirpstack/chirpstack-docker` — confirme que linhas 44/47 permanecem e são as únicas ocorrências de "chirpstack-docker").

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: reorganizar estrutura em domínios funcionais (platform, infrastructure, firmware) e atualizar PRD"
```

Nota: `git add -A` inclui também as mudanças pendentes do PRD (deleção de `PRD_PLATAFORMA_SAAS_IOT.md` + novo `PRD_PLATAFORMA_IOT.md`) — decisão do usuário.

---

## Task 3: Atualizar README do platform

**Files:**
- Modify: `platform/README.md`

- [ ] **Step 1: Atualizar referências**

Em `platform/README.md`:
- Linha 45: árvore `chirpstack-dashboard/` → `platform/`
- Linha 69: ``(ex.: `chirpstack-docker/`)`` → ``(ex.: `infrastructure/`)``

- [ ] **Step 2: Verificar**

Run:

```bash
grep -n "chirpstack-dashboard\|chirpstack-docker" platform/README.md
```

Expected: sem resultados.

- [ ] **Step 3: Commit**

```bash
git add platform/README.md
git commit -m "docs(platform): atualizar caminhos após reorganização"
```

---

## Task 4: Atualizar footer do webapp Flask

**Files:**
- Modify: `infrastructure/app/pagina.py`

- [ ] **Step 1: Atualizar o texto do rodapé**

Em `infrastructure/app/pagina.py`, linha 97:

```html
    <footer>Atualiza automática a cada 10s · infrastructure</footer>
```

(única mudança: `chirpstack-docker` → `infrastructure`)

- [ ] **Step 2: Commit**

```bash
git add infrastructure/app/pagina.py
git commit -m "chore(infrastructure): atualizar rodapé do webapp após renomeação"
```

---

## Task 5: Atualizar caminhos no plano ativo da Sprint 1

**Files:**
- Modify: `docs/superpowers/plans/2026-08-05-reestruturacao-multi-tenant.md`

- [ ] **Step 1: Substituir prefixo de caminho**

Em `docs/superpowers/plans/2026-08-05-reestruturacao-multi-tenant.md`, substituir **todas** as ocorrências de:

- `chirpstack-dashboard/backend` → `platform/backend`
- `chirpstack-dashboard/frontend` → `platform/frontend` (se houver)
- `chirpstack-dashboard/docker-compose.yml` → `platform/docker-compose.yml`

Use um editor com "replace all" (ocorrências: ~200). Verifique que **não** sobra nenhuma `chirpstack-dashboard`:

Run:

```bash
grep -c "chirpstack-dashboard" docs/superpowers/plans/2026-08-05-reestruturacao-multi-tenant.md
```

Expected: `0`.

- [ ] **Step 2: Atualizar a linha de Tech Stack (contexto)**

No cabeçalho do plano, linha 9: "Todas as mudanças em `chirpstack-dashboard/backend/`." → "Todas as mudanças em `platform/backend/`."

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-08-05-reestruturacao-multi-tenant.md
git commit -m "docs(plan): atualizar caminhos para a nova estrutura (platform)"
```

---

## Task 6: Atualizar issues #1–14 no GitHub

**Files:**
- GitHub issues #1–14 do milestone "Sprint 1 - Reestruturação Multi-Tenant"

- [ ] **Step 1: Verificar corpo de uma issue**

Run:

```bash
gh issue view 1 --repo IncludeLuisFerreira/Servidor-LoRaWAN --json body --jq '.body' | grep -c "chirpstack-dashboard"
```

Expected: número > 0 (as issues referenciam `chirpstack-dashboard/backend/...`).

- [ ] **Step 2: Atualizar cada issue #1–14**

Para cada issue `N` de 1 a 14, baixar o corpo, substituir `chirpstack-dashboard` → `platform` e reenviar:

```bash
gh issue view N --repo IncludeLuisFerreira/Servidor-LoRaWAN --json body --jq '.body' | sed 's/chirpstack-dashboard/platform/g' > /tmp/opencode/issue-N.md
gh issue edit N --repo IncludeLuisFerreira/Servidor-LoRaWAN --body-file /tmp/opencode/issue-N.md
```

(Execute para N = 1, 2, ..., 14. O `sed` com `s/.../platform/g` preserva o sufixo `/backend/...` pois substitui apenas o token `chirpstack-dashboard`.)

- [ ] **Step 3: Verificar**

Run:

```bash
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14; do
  c=$(gh issue view $n --repo IncludeLuisFerreira/Servidor-LoRaWAN --json body --jq '.body' | grep -c "chirpstack-dashboard" || true)
  echo "issue $n: $c ocorrências"
done
```

Expected: todas `0`.

---

## Task 7: Verificação final

- [ ] **Step 1: Confirmar estrutura e ausência de referências quebradas**

Run (from repo root):

```bash
git status --short
git ls-files | grep -E "chirpstack-dashboard|chirpstack-docker|^ESP_" || echo "OK: nenhuma pasta antiga rastreada"
```

Expected: working tree limpo (após commits), nenhum arquivo rastreado em pastas antigas. Únicas ocorrências legítimas de "chirpstack-docker" são as URLs upstream no `README.md` (linhas 44/47) e nos docs históricos 2026-07-30.

- [ ] **Step 2: Confirmar que o código continua saudável**

Run (from `platform/backend`):

```bash
npm run typecheck && npm test
```

Expected: typecheck OK, suíte Vitest verde.

- [ ] **Step 3: Confirmar estrutura final**

Run (from repo root):

```bash
ls
ls firmware
```

Expected:

```
docs/  firmware/  infrastructure/  platform/  PRD_PLATAFORMA_IOT.md  README.md  ...
firmware: end-device  gateway
```

- [ ] **Step 4: Log dos commits da reorganização**

Run:

```bash
git log --oneline -7
```

Expected: os 5 commits das Tasks 2–6 (Task 1 é o primeiro commit da Task 2 Step 4) com mensagens descritivas.

---

## Self-Review

1. **Cobertura do spec:** cada seção do spec tem task correspondente — estrutura-alvo (Task 1), README raiz (Task 2), README platform (Task 3), footer Flask (Task 4), plano ativo (Task 5), issues (Task 6), verificação (Task 7).
2. **Placeholders:** nenhum "TBD"/"TODO"; todos os passos têm comandos exatos.
3. **Consistência:** renomeações em Tasks 1 e referências nas Tasks 2–6 usam os mesmos nomes (`platform`, `infrastructure`, `firmware/end-device`, `firmware/gateway`, `end-device.ino`, `gateway.ino`).
