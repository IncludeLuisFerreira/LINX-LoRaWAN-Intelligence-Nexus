# ChirpStack Dashboard

![Node](https://img.shields.io/badge/backend-Node.js%20%2F%20TypeScript-339933)
![React](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB)
![TimescaleDB](https://img.shields.io/badge/db-PostgreSQL%20%2B%20TimescaleDB-336791)
![WebSocket](https://img.shields.io/badge/realtime-Socket.io-010101)
![Docker](https://img.shields.io/badge/infra-Docker%20Compose-2496ED)

Dashboard em tempo real para monitorar telemetria LoRaWAN recebida via **ChirpStack**
(MQTT). Consome os uplinks do broker, persiste em banco otimizado para séries
temporais, transmite leituras via WebSocket e dispara alertas por threshold com
cooldown via **Telegram** e/ou **E-mail**.

## Funcionalidades

- **Consumo MQTT** — assina `application/+/device/+/event/up` com reconexão automática e parser defensivo do payload v4 do ChirpStack.
- **Persistência em séries temporais** — leituras gravadas em batch (não-bloqueante) numa `hypertable` do TimescaleDB.
- **Dashboard real-time** — cards de status Online/Offline por dispositivo, gráfico temporal com seletor de métrica e histórico com busca/paginação.
- **Alertas com cooldown** — regras genéricas (`metrica:operador:valor`) com intervalo mínimo configurável por device+métrica.
- **Notificações** — Telegram (Bot API) e/ou E-mail (SMTP), ativáveis independentemente via variáveis de ambiente.
- **Tema Dark/Light** — alternância integrada.

## Arquitetura

```
ESP32 (OTAA) → Gateway → ChirpStack → Mosquitto (application/+/device/+/event/up)
                                        │
                                        ▼
                    Backend (Node/TS)  ── MQTT.js (reconnect automático)
                     ├─ Parser JSON v4 defensivo
                     ├─ PersistService ── fila → batch INSERT → TimescaleDB
                     ├─ LiveService ──── Socket.io → `telemetry:new`
                     ├─ ThresholdEngine ── cooldown por device+métrica
                     │    ├─ TelegramNotifier (Bot API)
                     │    └─ EmailNotifier (SMTP/Nodemailer)
                     └─ REST API ──────── /api/telemetry, /api/devices, /api/alerts
                              │
                              ▼
                    Frontend React (Vite + Tailwind + Recharts)
```

## Estrutura do projeto

```
platform/
├── docker-compose.yml        # backend + postgres (TimescaleDB) + frontend (nginx)
├── .env.example              # todas as variáveis de ambiente
├── backend/                  # Node.js/TypeScript
│   └── src/
│       ├── index.ts          # orquestração (HTTP + Socket.io + MQTT)
│       ├── config/env.ts     # validação de ambiente (zod)
│       ├── mqtt/             # cliente MQTT + parser v4
│       ├── db/               # pool, migrate e init.sql (schema TimescaleDB)
│       ├── repositories/     # acesso a dados (telemetry, device, alert)
│       ├── services/         # persistência em batch, live, threshold engine
│       ├── alerts/           # notificadores Telegram/E-mail + factory
│       └── routes/           # API REST
└── frontend/                 # React (Vite + TailwindCSS + Recharts)
    └── src/
        ├── api/              # cliente REST
        ├── socket/           # Socket.io-client
        ├── hooks/            # useTelemetrySocket (buffer real-time)
        └── components/       # Header, DeviceCards, RealtimeChart, HistoryTable, AlertsPanel
```

## Requisitos

- Docker + Docker Compose
- Stack ChirpStack em execução (ex.: `infrastructure/`) com broker MQTT acessível na porta 1883

## Execução rápida

```bash
cp .env.example .env        # primeira vez
docker compose up -d --build
```

Acesse:

| Serviço | URL |
|---------|-----|
| Dashboard | http://localhost:5173 |
| API / health | http://localhost:4000/api/health |

Parar: `docker compose down` · Logs: `docker compose logs -f backend`

## Configuração (`.env`)

| Variável | Default | Descrição |
|---|---|---|
| `PORT` | `4000` | Porta do backend |
| `MQTT_URL` | `mqtt://host.docker.internal:1883` | Broker do ChirpStack |
| `MQTT_TOPIC` | `application/+/device/+/event/up` | Tópico de uplink |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | vazio | Credenciais opcionais do broker |
| `DATABASE_URL` | `postgres://dashboard:dashboard@postgres:5432/dashboard` | Conexão PostgreSQL |
| `DB_POOL_MAX` | `10` | Tamanho do pool de conexões |
| `PERSIST_FLUSH_MS` | `1000` | Intervalo de flush em lote |
| `PERSIST_BATCH_SIZE` | `200` | Tamanho máximo do batch |
| `QUEUE_MAX_SIZE` | `5000` | Limite da fila de persistência (drop-oldest) |
| `OFFLINE_THRESHOLD_MINUTES` | `5` | Tempo sem uplink para marcar o device como Offline |
| `THRESHOLD_RULES` | vazio | Regras de alerta (ver abaixo) |
| `ALERT_COOLDOWN_MINUTES` | `5` | Intervalo mínimo entre alertas do mesmo device+métrica |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | vazio | Ativa Telegram |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURE` | vazio | Ativa E-mail |
| `SMTP_USER` / `SMTP_PASS` | vazio | Auth SMTP |
| `ALERT_EMAIL_FROM` / `ALERT_EMAIL_TO` | vazio | Remetente / destinatário |
| `CORS_ORIGIN` | vazio | Origem permitida (apenas dev) |

## Conectando ao broker MQTT do ChirpStack

Por padrão o backend usa `MQTT_URL=mqtt://host.docker.internal:1883` (o compose
adiciona `extra_hosts: host-gateway`), que alcança o Mosquitto exposto na porta
1883 do host — funciona sem tocar no stack existente.

Alternativa (rede Docker compartilhada): anexe o backend à rede do ChirpStack e use
`MQTT_URL=mqtt://mosquitto:1883`.

## Thresholds (alertas)

Formato: `THRESHOLD_RULES=metrica:operador:valor;...` — operadores `>`, `<`, `>=`, `<=`.

Métricas normalizadas pelo parser (toda chave numérica de `object` vira métrica):

- `ldr_value` — luminosidade (LDR)
- `temperature` / `humidity` — disponíveis quando o payload enviar
- `battery_level` — alias de `volt_bateria`

Exemplo:

```bash
THRESHOLD_RULES=ldr_value:>:500;battery_level:<:3.2
ALERT_COOLDOWN_MINUTES=5
```

O alerta é registrado no banco e enviado pelos canais ativados. Um novo alerta para
o mesmo device+métrica só é enviado após o cooldown expirar.

## API

| Endpoint | Descrição |
|---|---|
| `GET /api/health` | Status do serviço e do banco |
| `GET /api/telemetry?device_eui=&from=&to=&limit=&offset=` | Histórico paginado |
| `GET /api/devices` | Dispositivos com status Online/Offline |
| `GET /api/alerts?limit=&offset=` | Alertas registrados |

WebSocket: o backend emite `telemetry:new` com cada leitura normalizada em tempo real.

## Desenvolvimento local

Backend (porta 4000):

```bash
cd backend
npm install
npm run dev
```

Frontend (porta 5173, proxy `/api` e `/socket.io` → 4000):

```bash
cd frontend
npm install
npm run dev
```

Testes:

```bash
cd backend
npm test
```

## Solução de problemas

| Problema | Causa provável | Solução |
|---|---|---|
| `/api/health` mostra `db: down` | Postgres ainda subindo | Aguarde o `healthcheck` do compose e reinicie o backend |
| Nenhum dispositivo aparece | Broker MQTT inacessível | Confira `MQTT_URL`; teste com `mosquitto_pub -h localhost -p 1883 -t application/1/device/x/event/up -m '{"deviceInfo":{"deviceEui":"x"}}'` |
| Device sempre Offline | Uplinks com timestamp antigo ou sem uplinks recentes | Verifique `OFFLINE_THRESHOLD_MINUTES` e o clock do device |
| Alerta não chega no Telegram/E-mail | Canal não configurado | Preencha `TELEGRAM_*` ou `SMTP_*` no `.env` e recrie o container |
