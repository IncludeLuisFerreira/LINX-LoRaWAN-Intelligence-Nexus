# Design — Dashboard LoRaWAN (ChirpStack) em Tempo Real

Data: 2026-07-30
Branch: `plataforma-iot-integrada`

## Objetivo

Aplicação web end-to-end para monitoramento e visualização em tempo real de dados de
telemetria recebidos via LoRaWAN (ChirpStack), incluindo persistência em banco otimizado
para séries temporais, alertas por threshold com cooldown (Telegram + E-mail) e
containerização completa via Docker Compose. Todo o código fica dentro da pasta
`chirpstack-dashboard/` na raiz do workspace.

## Stack (confirmada: Proposta A)

- **Backend**: Node.js + TypeScript + Express + MQTT.js + Socket.io (processo único:
  HTTP + WebSocket + consumidor MQTT — alta vazão sem overhead de serialização).
- **Banco**: PostgreSQL com extensão TimescaleDB (`hypertable` otimizada para séries temporais).
- **Frontend**: React + Vite + TailwindCSS + Recharts + Socket.io-client.
- **Alertas**: Telegram Bot API + E-mail (Nodemailer/SMTP), ativáveis independentemente.
- **Infra**: Docker + Docker Compose.

## Integração com o stack existente

O repositório já contém `chirpstack-docker/` (ChirpStack 4 + Mosquitto em `mosquitto:1883`).
O backend do dashboard assina o tópico `application/+/device/+/event/up` do MQTT.

O device atual (ESP32, OTAA) envia no payload `object`: `ldr_value` (luminosidade) e
`volt_bateria`. O parser é genérico: toda chave numérica em `object` vira uma métrica
monitorável, permitindo `temperature`/`humidity` no futuro sem mudança de código.
Aliases normalizados pelo parser: `volt_bateria` → `battery_level`; demais chaves
preservam o nome original (`ldr_value`, `temperature`, `humidity`, etc.).

## Arquitetura e Fluxo de Dados

```
ESP32 (OTAA) → Gateway → ChirpStack → Mosquitto (application/+/device/+/event/up)
                                        │
                                        ▼
                    Backend (Node/TS)  ── MQTT.js (reconnect automático)
                     ├─ Parser JSON v4 defensivo (falha não derruba)
                     ├─ PersistService ── fila em memória → batch INSERT → TimescaleDB
                     ├─ LiveService ──── Socket.io → broadcast `telemetry:new`
                     ├─ ThresholdEngine ── cooldown por device+métrica
                     │    ├─ TelegramNotifier (Bot API)
                     │    └─ EmailNotifier (Nodemailer/SMTP)
                     └─ REST API ──────── /api/telemetry, /api/devices, /api/alerts
                              │
                              ▼
                    Frontend React (Vite + Tailwind + Recharts)
```

## Banco de Dados

Schema em `chirpstack-dashboard/backend/src/db/init.sql`, executado de forma idempotente
no boot do backend.

### `telemetry` (hypertable TimescaleDB)

Colunas: `id BIGSERIAL`, `device_eui TEXT NOT NULL`, `device_name TEXT NOT NULL`,
`application_id TEXT`, `temperature DOUBLE PRECISION`, `humidity DOUBLE PRECISION`,
`battery_level DOUBLE PRECISION`, `rssi INTEGER`, `snr DOUBLE PRECISION`,
`fcnt BIGINT`, `payload JSONB`, `timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()`.

- `create_hypertable('telemetry', 'timestamp', if_not_exists => TRUE)`.
- Índice `(device_eui, timestamp DESC)`.

### `devices`

PK `device_eui`. Upsert a cada uplink com `device_name`, `application_id`,
`last_seen_at`, `last_rssi`, `last_snr`. Status Online/Offline = `last_seen_at` dentro de
`OFFLINE_THRESHOLD_MINUTES` (env, default 5).

### `alerts`

Histórico de alertas: `id`, `device_eui`, `metric`, `value`, `threshold`, `channel`,
`sent_at`, `cooldown_until`.

## Backend (Módulos)

```
backend/src/
├── index.ts                  # entry: HTTP + Socket.io + inicia MQTT/persist/engine
├── config/env.ts             # parsing e validação de env vars
├── mqtt/client.ts            # conexão MQTT + reconnect automático
├── mqtt/parser.ts            # parser JSON v4 defensivo
├── db/pool.ts                # pg Pool + retry de conexão
├── db/migrate.ts             # executa init.sql no boot
├── db/init.sql
├── repositories/telemetryRepository.ts
├── repositories/deviceRepository.ts
├── repositories/alertRepository.ts
├── services/persistService.ts    # fila em memória + batch INSERT (não-bloqueante)
├── services/liveService.ts       # broadcast Socket.io
├── services/thresholdEngine.ts   # regras + cooldown por device+métrica
├── alerts/telegramNotifier.ts
├── alerts/emailNotifier.ts
├── alerts/index.ts               # factory: ativa canais conforme env
├── routes/telemetry.ts           # GET /api/telemetry (paginação/busca/período)
├── routes/devices.ts             # GET /api/devices (status online/offline)
├── routes/alerts.ts              # GET /api/alerts
└── utils/logger.ts
```

### Parser (`mqtt/parser.ts`)

Extrai do payload v4: `deviceInfo.deviceEUI/deviceName/applicationId`, `fCnt`,
`rxInfo[0].rssi/snr` e todas as chaves numéricas de `object` como métricas. Payload
malformado → log de erro e descarte (nunca crash).

### Persistência (`persistService.ts`)

Fila em memória de leituras; flush em batch a cada 1s ou 200 itens. Sem bloqueio no
event loop do ingest. Em caso de erro no INSERT, retry com backoff simples; fila com
tamanho máximo (drop-oldest + warn) para proteção sob pico.

### Threshold Engine (`thresholdEngine.ts`)

- Env `THRESHOLD_RULES` ex.: `ldr_value:>:500;temperature:>:35;battery_level:<:3.2`.
  Formato: `metrica:operador:valor`, separado por `;`. Operadores: `>`, `<`, `>=`, `<=`.
- Cooldown por par device+métrica: `ALERT_COOLDOWN_MINUTES` (default 5), controlado pela
  tabela `alerts.cooldown_until`.
- Ao disparar: registra alerta e envia via canais ativados.

### Notificadores

- **Telegram**: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`; POST
  `https://api.telegram.org/bot<token>/sendMessage`.
- **E-mail**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_SECURE`,
  `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO`; Nodemailer com HTML formatado.
- Mensagem inclui: device, métrica, valor, limite, timestamp, RSSI/SNR.
- Falha de envio → log, não interrompe o ingest.

### REST API

- `GET /api/health`
- `GET /api/telemetry?device_eui=&limit=&offset=&from=&to=` (histórico paginado)
- `GET /api/devices` (lista com status online/offline + última leitura)
- `GET /api/alerts?limit=&offset=`

### Socket.io

Emite `telemetry:new` (leitura normalizada) para todos os clientes conectados.

## Frontend (Módulos)

```
frontend/src/
├── main.tsx / App.tsx
├── api/client.ts              # REST client
├── socket/socket.ts           # Socket.io-client
├── hooks/useTelemetrySocket.ts
├── types.ts
└── components/
    ├── Header.tsx             # título + status da conexão + theme toggle
    ├── DeviceCards.tsx        # cards de status por dispositivo
    ├── MetricCard.tsx
    ├── RealtimeChart.tsx      # Recharts LineChart com seletor de métrica
    ├── HistoryTable.tsx       # tabela com busca + paginação
    └── AlertsPanel.tsx        # alertas recentes
```

- Cards: nome do device, Online/Offline, luminosidade, bateria, RSSI/SNR, última leitura.
- Gráfico real-time alimentado por `telemetry:new`; seletor de métrica
  (luminosidade/temperatura/umidade/bateria/RSSI/SNR).
- Tabela de histórico via REST paginado + busca por device + filtro de período.
- Tema Dark (default) / Light via classe `dark` do Tailwind.
- Em produção o frontend é servido pelo container nginx (single origin): nginx entrega o
  build estático e faz proxy de `/api` e `/socket.io` para o backend — sem CORS.

## Docker & Deploy

`chirpstack-dashboard/docker-compose.yml` orquestra:

- `backend`: build `./backend`, expõe porta (ex.: `4000`), `extra_hosts:
  host.docker.internal:host-gateway` para alcançar o Mosquitto do stack existente
  via `MQTT_URL=mqtt://host.docker.internal:1883` (default no `.env.example`).
  Alternativa documentada no README: anexar o backend à rede do `chirpstack-docker` e
  usar `mqtt://mosquitto:1883`.
- `postgres`: imagem `timescale/timescaledb:latest-pg14`, volume nomeado.
- `frontend`: multi-stage build (Node → nginx) servindo o static; proxy `/api` e
  `/socket.io` para o backend.

`.env.example` com todas as variáveis (MQTT, DB, Telegram, SMTP, thresholds, cooldown,
offline threshold). `README.md` em PT-BR com instruções de execução
(`docker-compose up -d`).

## Variáveis de Ambiente

| Variável | Default | Descrição |
|---|---|---|
| `MQTT_URL` | `mqtt://host.docker.internal:1883` | Broker do ChirpStack |
| `MQTT_TOPIC` | `application/+/device/+/event/up` | Tópico de uplink |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | vazio | Credenciais opcionais |
| `DATABASE_URL` | `postgres://dashboard:dashboard@postgres:5432/dashboard` | Conexão PostgreSQL |
| `DB_POOL_MAX` | 10 | Pool de conexões |
| `PERSIST_FLUSH_MS` | 1000 | Intervalo de flush em lote |
| `PERSIST_BATCH_SIZE` | 200 | Tamanho máximo do batch |
| `QUEUE_MAX_SIZE` | 5000 | Tamanho máximo da fila de persistência |
| `OFFLINE_THRESHOLD_MINUTES` | 5 | Tempo para device ficar Offline |
| `THRESHOLD_RULES` | vazio | `metrica:operador:valor;...` |
| `ALERT_COOLDOWN_MINUTES` | 5 | Cooldown por device+métrica |
| `TELEGRAM_BOT_TOKEN` | vazio | Desativa Telegram se vazio |
| `TELEGRAM_CHAT_ID` | vazio | Chat de destino |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURE` | vazio | Desativa E-mail se vazio |
| `SMTP_USER` / `SMTP_PASS` | vazio | Auth SMTP |
| `ALERT_EMAIL_FROM` / `ALERT_EMAIL_TO` | vazio | Remetente/destinatário |
| `PORT` | 4000 | Porta do backend |
| `CORS_ORIGIN` | vazio | Origem permitida (dev) |

## Tratamento de Erros

- MQTT: reconnect automático (MQTT.js).
- Banco: pool + retry no boot; INSERT em batch com retry/backoff.
- Parser: defensivo, descarta payload inválido sem crash.
- Notificadores: falhas logadas, não bloqueiam ingest.

## Testes

Backend (Vitest):

- `parser`: payload v4 válido, campos ausentes, JSON inválido.
- `thresholdEngine`: disparo acima/abaixo do limite, operadores, cooldown respeitado.
- `persistService`: batch flush, drop-oldest quando fila cheia.

Frontend: `tsc --noEmit` + `vite build`.

## Fora de Escopo (nesta fase)

- Autenticação/autorização de usuários no dashboard.
- Envio de downlinks (controle de dispositivo) pelo dashboard.
- Migrações versionadas avançadas do schema (usado `init.sql` idempotente).
