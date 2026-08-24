# Design — Reorganização da Estrutura do Repositório em Domínios Funcionais

Data: 2026-08-05
Branch: `plataforma-iot-integrada`
Status: Aprovado

## Objetivo

Reorganizar a estrutura de arquivos do repositório `IncludeLuisFerreira/Servidor-LoRaWAN`
para nomes de pastas mais descritivos e profissionais, agrupando por domínio funcional,
de modo a preparar a base para a reestruturação multi-tenant (Sprint 1 — Etapa 1 do PRD).

## Decisões aprovadas

- **Abordagem A — Domínios funcionais** (raiz limpa com 4 pastas de domínio).
- **Nomes em inglês** (padrão de mercado).
- **Renomear + atualizar referências** em issues, plano ativo, README e código.
- **Renomear sketches Arduino** para casar com os nomes das pastas (exigência do Arduino IDE).
- **Renomear nomes dos pacotes npm** para refletir a nova estrutura.
- **Manter docs históricos (2026-07-30) inalterados** — registro de trabalho concluído.

## Estrutura-alvo

```
LoraWan-project/
├── platform/                        # SaaS multi-tenant (antes chirpstack-dashboard/)
│   ├── README.md · .env · .env.example · .gitignore · docker-compose.yml
│   ├── backend/                     # package name → platform-backend
│   └── frontend/                    # package name → platform-frontend
├── infrastructure/                  # Stack ChirpStack Docker (antes chirpstack-docker/)
│   ├── README.md · LICENSE · Makefile · .gitattributes · docker-compose.yml
│   ├── app/                         # webapp Flask
│   └── configuration/
├── firmware/
│   ├── end-device/                  # antes ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR/
│   │   └── end-device.ino           # renomeado do sketch principal
│   └── gateway/                     # antes ESP_sc_gway_pk/
│       └── gateway.ino              # renomeado do sketch principal
├── docs/                            # inalterado
├── PRD_PLATAFORMA_IOT.md            # permanece na raiz
├── README.md                        # atualizado com novos caminhos
└── .github/ · .vscode/ · .gitignore # inalterados
```

## Mapeamento de renomeações

| De | Para | Tipo |
|----|------|------|
| `chirpstack-dashboard/` | `platform/` | mover |
| `chirpstack-docker/` | `infrastructure/` | mover |
| `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR/` | `firmware/end-device/` | mover |
| `ESP_sc_gway_pk/` | `firmware/gateway/` | mover |
| `ESP-End-Device-LORAWAN-ABP-ESP32-RFM95-LDR.ino` | `firmware/end-device/end-device.ino` | renomear sketch |
| `ESP_sc_gway_pk.ino` | `firmware/gateway/gateway.ino` | renomear sketch |
| `chirpstack-dashboard-backend` (package.json) | `platform-backend` | renomear |
| `chirpstack-dashboard-frontend` (package.json) | `platform-frontend` | renomear |

## Referências a atualizar

1. **README.md raiz** — todos os caminhos:
   - `chirpstack-dashboard/` → `platform/`
   - `chirpstack-docker/` → `infrastructure/`
   - Sketches renomeados (`ESP_sc_gway_pk.ino` → `gateway.ino`, `ESP-End-Device-....ino` → `end-device.ino`)
   - Seção "Estrutura" no fim do arquivo.
2. **`docs/superpowers/plans/2026-08-05-reestruturacao-multi-tenant.md`** — todos os caminhos `chirpstack-dashboard/backend/...` → `platform/backend/...` (plano ativo da Sprint 1).
3. **Issues #1–14 no GitHub** — corpos referenciam `chirpstack-dashboard/backend/...`; atualizar para `platform/backend/...` via `gh issue edit`.
4. **`platform/README.md`** — referências internas a caminhos antigos.
5. **`infrastructure/app/pagina.py`** — footer cosmético `chirpstack-docker` → `infrastructure`.

## Fora de escopo

- Alteração de conteúdo do PRD (sem referências de caminho).
- Docs históricos 2026-07-30 (mantidos como registro).
- Reorganização interna de `platform/backend/src` ou `platform/frontend/src` (Sprint 1 já cobre isso nas issues).
- Código TS/TSX (nenhuma referência a caminhos raiz foi encontrada fora de docs/README/package.json).

## Estratégia de movimentação

- Usar `mv` do sistema para mover pastas inteiras (preserva `node_modules/`, `venv/`, `dist/`, `__pycache__/` não rastreados).
- Após mover, `git add -A` e commit único descritivo.
- Não rastreados seguem ignorados pelo `.gitignore` (não são movidos pelo git).

## Verificação pós-mudança

- `git status` limpo com a nova estrutura rastreada.
- `git ls-files | grep -E "chirpstack-dashboard|chirpstack-docker|ESP_"` não retorna referências de caminho (exceto docs históricos intencionais e `github.com/chirpstack/chirpstack-docker` no README).
- Nenhum arquivo de código quebrado (backend typecheck e testes seguem verde após mover; verificar com `npm test`/`npm run typecheck` em `platform/backend`).
- Issues #1–14 atualizadas com os novos caminhos.
