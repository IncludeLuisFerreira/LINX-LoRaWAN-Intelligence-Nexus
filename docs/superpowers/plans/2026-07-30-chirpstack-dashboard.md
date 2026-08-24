# ChirpStack Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready real-time LoRaWAN telemetry dashboard (backend Node/TS + TimescaleDB, frontend React/Vite/Tailwind, Telegram+Email alerts, Docker Compose) inside `chirpstack-dashboard/`.

**Architecture:** A single Node.js/TypeScript process consumes ChirpStack MQTT uplinks (`application/+/device/+/event/up`), parses the v4 JSON payload defensively, persists readings in batches to a TimescaleDB hypertable, broadcasts via Socket.io, and evaluates generic threshold rules with per-device cooldown that notify via Telegram and/or Email. A React SPA (Vite + Tailwind + Recharts) renders cards, a live chart, and a paginated history table. Docker Compose orchestrates backend, postgres+TimescaleDB, and an nginx frontend.

**Tech Stack:** Node.js 20 + TypeScript + Express + MQTT.js + Socket.io + pg + zod + nodemailer (backend, Vitest tests); React 18 + Vite 5 + TailwindCSS 3 + Recharts + socket.io-client (frontend); PostgreSQL + TimescaleDB; Docker Compose.

**Branch:** `plataforma-iot-integrada` (already created). All work happens inside the new `chirpstack-dashboard/` directory.

**MQTT context:** Existing stack at `chirpstack-docker/` exposes Mosquitto on host port 1883. From Docker the backend reaches it via `mqtt://host.docker.internal:1883` (with `extra_hosts: host-gateway`).

---

## File Structure

```
chirpstack-dashboard/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── backend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── src/
│   │   ├── index.ts
│   │   ├── types.ts
│   │   ├── config/env.ts
│   │   ├── utils/logger.ts
│   │   ├── mqtt/client.ts
│   │   ├── mqtt/parser.ts
│   │   ├── db/pool.ts
│   │   ├── db/migrate.ts
│   │   ├── db/init.sql
│   │   ├── repositories/telemetryRepository.ts
│   │   ├── repositories/deviceRepository.ts
│   │   ├── repositories/alertRepository.ts
│   │   ├── services/persistService.ts
│   │   ├── services/liveService.ts
│   │   ├── services/rules.ts
│   │   ├── services/thresholdEngine.ts
│   │   ├── alerts/telegramNotifier.ts
│   │   ├── alerts/emailNotifier.ts
│   │   ├── alerts/index.ts
│   │   └── routes/
│   │       ├── health.ts
│   │       ├── telemetry.ts
│   │       ├── devices.ts
│   │       └── alerts.ts
│   └── test/
│       ├── parser.test.ts
│       ├── env.test.ts
│       ├── rules.test.ts
│       ├── thresholdEngine.test.ts
│       └── persistService.test.ts
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    ├── Dockerfile
    ├── nginx.conf
    ├── .dockerignore
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── types.ts
        ├── api/client.ts
        ├── socket/socket.ts
        ├── hooks/useTelemetrySocket.ts
        └── components/
            ├── Header.tsx
            ├── MetricCard.tsx
            ├── DeviceCards.tsx
            ├── RealtimeChart.tsx
            ├── HistoryTable.tsx
            └── AlertsPanel.tsx
```

---

## Task 1: Scaffold backend project

**Files:**
- Create: `chirpstack-dashboard/backend/package.json`
- Create: `chirpstack-dashboard/backend/tsconfig.json`
- Create: `chirpstack-dashboard/backend/vitest.config.ts`
- Create: `chirpstack-dashboard/backend/.dockerignore`
- Create: `chirpstack-dashboard/backend/src/utils/logger.ts`

- [ ] **Step 1: Create the package.json**

`chirpstack-dashboard/backend/package.json`:

```json
{
  "name": "chirpstack-dashboard-backend",
  "version": "1.0.0",
  "private": true,
  "main": "dist/index.js",
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc && cp src/db/init.sql dist/db/init.sql",
    "start": "node dist/index.js",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "express": "^4.19.2",
    "mqtt": "^5.7.0",
    "nodemailer": "^6.9.13",
    "pg": "^8.11.5",
    "socket.io": "^4.7.5",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/node": "^20.14.0",
    "@types/nodemailer": "^6.4.15",
    "@types/pg": "^8.11.6",
    "tsx": "^4.16.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create the tsconfig.json**

`chirpstack-dashboard/backend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "Node",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create the vitest config**

`chirpstack-dashboard/backend/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
})
```

- [ ] **Step 4: Create the .dockerignore**

`chirpstack-dashboard/backend/.dockerignore`:

```
node_modules
dist
.env
```

- [ ] **Step 5: Create the logger util**

`chirpstack-dashboard/backend/src/utils/logger.ts`:

```ts
const ts = (): string => new Date().toISOString()

export const logger = {
  info: (msg: string): void => console.log(`[${ts()}] [info] ${msg}`),
  warn: (msg: string): void => console.warn(`[${ts()}] [warn] ${msg}`),
  error: (msg: string, err?: unknown): void =>
    console.error(`[${ts()}] [error] ${msg}`, err instanceof Error ? err.stack ?? err.message : err ?? ''),
}
```

- [ ] **Step 6: Install dependencies and verify**

Run (from `chirpstack-dashboard/backend`):

```bash
npm install
```

Expected: `npm install` completes with no errors, creating `package-lock.json` and `node_modules/`.

- [ ] **Step 7: Verify typecheck runs**

Run:

```bash
npx tsc --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 8: Commit**

```bash
git add chirpstack-dashboard/backend
git commit -m "chore(backend): scaffold Node/TS project (express, mqtt, socket.io, pg, vitest)"
```

---

## Task 2: Environment configuration (env.ts) with tests

**Files:**
- Create: `chirpstack-dashboard/backend/src/config/env.ts`
- Test: `chirpstack-dashboard/backend/test/env.test.ts`

- [ ] **Step 1: Write the failing test**

`chirpstack-dashboard/backend/test/env.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'

describe('env', () => {
  const originalEnv = process.env

  beforeEach(() => {
    vi.resetModules()
    process.env = { ...originalEnv }
  })

  it('aplica defaults quando variáveis não são informadas', async () => {
    for (const key of [
      'PORT', 'MQTT_URL', 'MQTT_TOPIC', 'DATABASE_URL', 'PERSIST_FLUSH_MS',
      'PERSIST_BATCH_SIZE', 'QUEUE_MAX_SIZE', 'OFFLINE_THRESHOLD_MINUTES',
      'ALERT_COOLDOWN_MINUTES',
    ]) {
      delete process.env[key]
    }
    const { env } = await import('../src/config/env')
    expect(env.PORT).toBe(4000)
    expect(env.MQTT_URL).toBe('mqtt://host.docker.internal:1883')
    expect(env.MQTT_TOPIC).toBe('application/+/device/+/event/up')
    expect(env.PERSIST_FLUSH_MS).toBe(1000)
    expect(env.PERSIST_BATCH_SIZE).toBe(200)
    expect(env.QUEUE_MAX_SIZE).toBe(5000)
    expect(env.OFFLINE_THRESHOLD_MINUTES).toBe(5)
    expect(env.ALERT_COOLDOWN_MINUTES).toBe(5)
  })

  it('faz coerção de tipos numéricos', async () => {
    process.env.PORT = '8080'
    process.env.PERSIST_FLUSH_MS = '250'
    const { env } = await import('../src/config/env')
    expect(env.PORT).toBe(8080)
    expect(env.PERSIST_FLUSH_MS).toBe(250)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `chirpstack-dashboard/backend`):

```bash
npx vitest run test/env.test.ts
```

Expected: FAIL — module `../src/config/env` not found / cannot be imported.

- [ ] **Step 3: Write the implementation**

`chirpstack-dashboard/backend/src/config/env.ts`:

```ts
import 'dotenv/config'
import { z } from 'zod'

const EnvSchema = z.object({
  PORT: z.coerce.number().default(4000),
  MQTT_URL: z.string().default('mqtt://host.docker.internal:1883'),
  MQTT_TOPIC: z.string().default('application/+/device/+/event/up'),
  MQTT_USERNAME: z.string().optional(),
  MQTT_PASSWORD: z.string().optional(),
  DATABASE_URL: z
    .string()
    .default('postgres://dashboard:dashboard@postgres:5432/dashboard'),
  DB_POOL_MAX: z.coerce.number().default(10),
  PERSIST_FLUSH_MS: z.coerce.number().default(1000),
  PERSIST_BATCH_SIZE: z.coerce.number().default(200),
  QUEUE_MAX_SIZE: z.coerce.number().default(5000),
  OFFLINE_THRESHOLD_MINUTES: z.coerce.number().default(5),
  THRESHOLD_RULES: z.string().default(''),
  ALERT_COOLDOWN_MINUTES: z.coerce.number().default(5),
  TELEGRAM_BOT_TOKEN: z.string().optional(),
  TELEGRAM_CHAT_ID: z.string().optional(),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z.coerce.number().optional(),
  SMTP_SECURE: z.coerce.boolean().default(false),
  SMTP_USER: z.string().optional(),
  SMTP_PASS: z.string().optional(),
  ALERT_EMAIL_FROM: z.string().optional(),
  ALERT_EMAIL_TO: z.string().optional(),
  CORS_ORIGIN: z.string().optional(),
})

const parsed = EnvSchema.safeParse(process.env)

if (!parsed.success) {
  console.error('[env] Configuração inválida:', JSON.stringify(parsed.error.flatten().fieldErrors, null, 2))
  process.exit(1)
}

export const env = parsed.data
export type Env = typeof env
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
npx vitest run test/env.test.ts
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add chirpstack-dashboard/backend/src/config chirpstack-dashboard/backend/test/env.test.ts
git commit -m "feat(backend): config de ambiente validada com zod"
```

---

## Task 3: Shared types + MQTT parser with tests

**Files:**
- Create: `chirpstack-dashboard/backend/src/types.ts`
- Create: `chirpstack-dashboard/backend/src/mqtt/parser.ts`
- Test: `chirpstack-dashboard/backend/test/parser.test.ts`

- [ ] **Step 1: Write the failing test**

`chirpstack-dashboard/backend/test/parser.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { parseUplink } from '../src/mqtt/parser'

const VALID_PAYLOAD = JSON.stringify({
  deviceInfo: {
    deviceEui: '0011223344556677',
    deviceName: 'esp32-ldr-01',
    applicationId: 'app-01',
  },
  fCnt: 42,
  rxInfo: [{ rssi: -72, snr: 8.5 }],
  time: '2026-07-30T12:00:00Z',
  object: { ldr_value: 412, volt_bateria: 3.9 },
})

describe('parseUplink', () => {
  it('parseia payload v4 válido e normaliza métricas', () => {
    const r = parseUplink(VALID_PAYLOAD)
    expect(r).not.toBeNull()
    expect(r!.deviceEui).toBe('0011223344556677')
    expect(r!.deviceName).toBe('esp32-ldr-01')
    expect(r!.applicationId).toBe('app-01')
    expect(r!.fCnt).toBe(42)
    expect(r!.rssi).toBe(-72)
    expect(r!.snr).toBe(8.5)
    expect(r!.metrics.ldr_value).toBe(412)
    expect(r!.metrics.battery_level).toBe(3.9)
    expect(r!.timestamp).toBe('2026-07-30T12:00:00Z')
  })

  it('aceita valores numéricos em string', () => {
    const r = parseUplink(
      JSON.stringify({
        deviceInfo: { deviceEui: 'aa' },
        object: { ldr_value: '300' },
      })
    )
    expect(r!.metrics.ldr_value).toBe(300)
  })

  it('rejeita JSON inválido com null', () => {
    expect(parseUplink('{not json')).toBeNull()
  })

  it('rejeita payload sem deviceEui', () => {
    expect(parseUplink(JSON.stringify({ fCnt: 1 }))).toBeNull()
  })

  it('ignora métricas não numéricas', () => {
    const r = parseUplink(
      JSON.stringify({
        deviceInfo: { deviceEui: 'aa' },
        object: { nome: 'sensor', ldr_value: 10 },
      })
    )
    expect(r!.metrics.nome).toBeUndefined()
    expect(r!.metrics.ldr_value).toBe(10)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `chirpstack-dashboard/backend`):

```bash
npx vitest run test/parser.test.ts
```

Expected: FAIL — cannot find module `../src/mqtt/parser`.

- [ ] **Step 3: Write the types**

`chirpstack-dashboard/backend/src/types.ts`:

```ts
export interface MetricValue {
  [metric: string]: number
}

export interface Reading {
  deviceEui: string
  deviceName: string
  applicationId: string
  fCnt?: number
  rssi?: number
  snr?: number
  metrics: MetricValue
  timestamp: string
  raw: unknown
}

export type ThresholdOperator = '>' | '<' | '>=' | '<='

export interface AlertEvent {
  deviceEui: string
  deviceName: string
  metric: string
  value: number
  threshold: number
  operator: ThresholdOperator
  timestamp: string
}

export interface AlertSender {
  send(event: AlertEvent): Promise<void>
}
```

- [ ] **Step 4: Write the parser implementation**

`chirpstack-dashboard/backend/src/mqtt/parser.ts`:

```ts
import type { MetricValue, Reading } from '../types'

const METRIC_ALIASES: Record<string, string> = {
  volt_bateria: 'battery_level',
  volt_battery: 'battery_level',
  battery: 'battery_level',
}

function toNumber(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v)
  return undefined
}

function parseTimestamp(payload: Record<string, unknown>): string {
  const time = payload.time
  const nsTime = payload.nsTime
  if (typeof time === 'string') return time
  if (typeof nsTime === 'string') return nsTime
  return new Date().toISOString()
}

/**
 * Parse defensivo do payload JSON v4 (ChirpStack) publicado no tópico de uplink.
 * Retorna null para payloads malformados — nunca lança exceção.
 */
export function parseUplink(rawPayload: string): Reading | null {
  let payload: Record<string, any>
  try {
    payload = JSON.parse(rawPayload)
  } catch {
    return null
  }
  if (!payload || typeof payload !== 'object') return null

  const deviceInfo = payload.deviceInfo
  const deviceEui = deviceInfo?.deviceEui
  if (typeof deviceEui !== 'string' || deviceEui === '') return null

  const metrics: MetricValue = {}
  const obj = payload.object
  if (obj && typeof obj === 'object') {
    for (const [key, value] of Object.entries(obj)) {
      const num = toNumber(value)
      if (num === undefined) continue
      const normalizedKey = METRIC_ALIASES[key] ?? key
      metrics[normalizedKey] = num
    }
  }

  const rx = Array.isArray(payload.rxInfo) && payload.rxInfo.length > 0 ? payload.rxInfo[0] : {}

  return {
    deviceEui,
    deviceName: typeof deviceInfo?.deviceName === 'string' ? deviceInfo.deviceName : deviceEui,
    applicationId: typeof deviceInfo?.applicationId === 'string' ? deviceInfo.applicationId : '',
    fCnt: toNumber(payload.fCnt),
    rssi: toNumber(rx.rssi),
    snr: toNumber(rx.snr),
    metrics,
    timestamp: parseTimestamp(payload),
    raw: payload,
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
npx vitest run test/parser.test.ts
```

Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add chirpstack-dashboard/backend/src/types.ts chirpstack-dashboard/backend/src/mqtt/parser.ts chirpstack-dashboard/backend/test/parser.test.ts
git commit -m "feat(backend): parser defensivo do payload v4 do ChirpStack"
```

---

## Task 4: Database — pool, migrate, init.sql

**Files:**
- Create: `chirpstack-dashboard/backend/src/db/pool.ts`
- Create: `chirpstack-dashboard/backend/src/db/migrate.ts`
- Create: `chirpstack-dashboard/backend/src/db/init.sql`

- [ ] **Step 1: Create the init.sql**

`chirpstack-dashboard/backend/src/db/init.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS telemetry (
  id BIGSERIAL,
  device_eui TEXT NOT NULL,
  device_name TEXT NOT NULL,
  application_id TEXT NOT NULL DEFAULT '',
  temperature DOUBLE PRECISION,
  humidity DOUBLE PRECISION,
  battery_level DOUBLE PRECISION,
  rssi INTEGER,
  snr DOUBLE PRECISION,
  fcnt BIGINT,
  payload JSONB,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('telemetry', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time ON telemetry (device_eui, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry (timestamp DESC);

CREATE TABLE IF NOT EXISTS devices (
  device_eui TEXT PRIMARY KEY,
  device_name TEXT NOT NULL,
  application_id TEXT NOT NULL DEFAULT '',
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_rssi INTEGER,
  last_snr DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  device_eui TEXT NOT NULL,
  metric TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  threshold DOUBLE PRECISION NOT NULL,
  channel TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cooldown_until TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts (sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_device_metric ON alerts (device_eui, metric);
```

- [ ] **Step 2: Create the pool**

`chirpstack-dashboard/backend/src/db/pool.ts`:

```ts
import { Pool } from 'pg'
import { env } from '../config/env'

export const pool = new Pool({
  connectionString: env.DATABASE_URL,
  max: env.DB_POOL_MAX,
  connectionTimeoutMillis: 5000,
  idleTimeoutMillis: 30000,
})

export async function waitForDb(retries = 10, delayMs = 3000): Promise<void> {
  for (let i = 1; i <= retries; i++) {
    try {
      await pool.query('SELECT 1')
      return
    } catch (err) {
      if (i === retries) throw err
      console.error(`[db] Conexão falhou (tentativa ${i}/${retries}), tentando novamente em ${delayMs}ms`)
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
  }
}
```

- [ ] **Step 3: Create the migrate module**

`chirpstack-dashboard/backend/src/db/migrate.ts`:

```ts
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { pool } from './pool'
import { logger } from '../utils/logger'

export async function migrate(): Promise<void> {
  const initPath = fileURLToPath(new URL('./init.sql', import.meta.url))
  const sql = await readFile(initPath, 'utf8')
  await pool.query(sql)
  logger.info('[db] Schema verificado (init.sql aplicado)')
}
```

- [ ] **Step 4: Verify the build copies init.sql to dist**

Run (from `chirpstack-dashboard/backend`):

```bash
npm run build && ls dist/db/init.sql
```

Expected: build succeeds and `dist/db/init.sql` exists.

- [ ] **Step 5: Commit**

```bash
git add chirpstack-dashboard/backend/src/db
git commit -m "feat(backend): pool postgres, migrate e schema timescaledb (init.sql)"
```

---

## Task 5: Repositories (telemetry, device, alert)

**Files:**
- Create: `chirpstack-dashboard/backend/src/repositories/telemetryRepository.ts`
- Create: `chirpstack-dashboard/backend/src/repositories/deviceRepository.ts`
- Create: `chirpstack-dashboard/backend/src/repositories/alertRepository.ts`

- [ ] **Step 1: Create the telemetry repository**

`chirpstack-dashboard/backend/src/repositories/telemetryRepository.ts`:

```ts
import { pool } from '../db/pool'
import type { Reading } from '../types'

export interface TelemetryRow {
  id: number
  device_eui: string
  device_name: string
  application_id: string
  temperature: number | null
  humidity: number | null
  battery_level: number | null
  rssi: number | null
  snr: number | null
  fcnt: number | null
  payload: unknown
  timestamp: string
}

const NUMERIC_COLUMNS = 11

export async function insertTelemetryBatch(readings: Reading[]): Promise<void> {
  if (readings.length === 0) return
  const values: unknown[] = []
  const rows: unknown[][] = []
  for (const r of readings) {
    rows.push([
      r.deviceEui,
      r.deviceName,
      r.applicationId,
      r.metrics.temperature ?? null,
      r.metrics.humidity ?? null,
      r.metrics.battery_level ?? null,
      r.rssi ?? null,
      r.snr ?? null,
      r.fCnt ?? null,
      JSON.stringify(r.raw),
      r.timestamp,
    ])
  }
  for (const row of rows) values.push(...row)
  const placeholders = rows
    .map((_, i) => {
      const base = i * NUMERIC_COLUMNS
      const parts: string[] = []
      for (let c = 1; c <= NUMERIC_COLUMNS; c++) parts.push(`$${base + c}`)
      return `(${parts.join(', ')})`
    })
    .join(', ')
  await pool.query(
    `INSERT INTO telemetry
       (device_eui, device_name, application_id, temperature, humidity, battery_level,
        rssi, snr, fcnt, payload, timestamp)
     VALUES ${placeholders}`,
    values
  )
}

export interface TelemetryQuery {
  deviceEui?: string
  from?: string
  to?: string
  limit: number
  offset: number
}

export async function queryTelemetry(
  q: TelemetryQuery
): Promise<{ rows: TelemetryRow[]; total: number }> {
  const conditions: string[] = []
  const params: unknown[] = []
  if (q.deviceEui) {
    params.push(q.deviceEui)
    conditions.push(`device_eui = $${params.length}`)
  }
  if (q.from) {
    params.push(q.from)
    conditions.push(`timestamp >= $${params.length}`)
  }
  if (q.to) {
    params.push(q.to)
    conditions.push(`timestamp <= $${params.length}`)
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

  const countResult = await pool.query<{ count: string }>(
    `SELECT COUNT(*)::text AS count FROM telemetry ${where}`,
    params
  )

  const limitIdx = params.length + 1
  const offsetIdx = params.length + 2
  params.push(q.limit, q.offset)

  const result = await pool.query<TelemetryRow>(
    `SELECT id, device_eui, device_name, application_id, temperature, humidity, battery_level,
            rssi, snr, fcnt, payload, timestamp
     FROM telemetry
     ${where}
     ORDER BY timestamp DESC
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    params
  )
  return { rows: result.rows, total: Number(countResult.rows[0]?.count ?? 0) }
}
```

- [ ] **Step 2: Create the device repository**

`chirpstack-dashboard/backend/src/repositories/deviceRepository.ts`:

```ts
import { pool } from '../db/pool'
import type { Reading } from '../types'

export interface DeviceRow {
  device_eui: string
  device_name: string
  application_id: string
  last_seen_at: string
  last_rssi: number | null
  last_snr: number | null
  created_at: string
}

export interface DeviceStatusRow extends DeviceRow {
  online: boolean
}

const DEVICE_COLUMNS = 6

export async function upsertDevices(readings: Reading[]): Promise<void> {
  if (readings.length === 0) return
  const values: unknown[] = []
  const rows: unknown[][] = []
  for (const r of readings) {
    rows.push([r.deviceEui, r.deviceName, r.applicationId, r.timestamp, r.rssi ?? null, r.snr ?? null])
  }
  for (const row of rows) values.push(...row)
  const placeholders = rows
    .map((_, i) => {
      const base = i * DEVICE_COLUMNS
      const parts: string[] = []
      for (let c = 1; c <= DEVICE_COLUMNS; c++) parts.push(`$${base + c}`)
      return `(${parts.join(', ')})`
    })
    .join(', ')
  await pool.query(
    `INSERT INTO devices (device_eui, device_name, application_id, last_seen_at, last_rssi, last_snr)
     VALUES ${placeholders}
     ON CONFLICT (device_eui) DO UPDATE SET
       device_name = EXCLUDED.device_name,
       application_id = EXCLUDED.application_id,
       last_seen_at = EXCLUDED.last_seen_at,
       last_rssi = EXCLUDED.last_rssi,
       last_snr = EXCLUDED.last_snr`,
    values
  )
}

export async function listDevices(offlineThresholdMinutes: number): Promise<DeviceStatusRow[]> {
  const result = await pool.query<DeviceStatusRow>(
    `SELECT device_eui, device_name, application_id, last_seen_at, last_rssi, last_snr, created_at,
            (last_seen_at > NOW() - make_interval(mins => $1)) AS online
     FROM devices
     ORDER BY last_seen_at DESC`,
    [offlineThresholdMinutes]
  )
  return result.rows
}
```

- [ ] **Step 3: Create the alert repository**

`chirpstack-dashboard/backend/src/repositories/alertRepository.ts`:

```ts
import { pool } from '../db/pool'

export interface AlertRow {
  id: number
  device_eui: string
  metric: string
  value: number
  threshold: number
  channel: string
  sent_at: string
  cooldown_until: string
}

export async function canAlert(deviceEui: string, metric: string): Promise<boolean> {
  const result = await pool.query<{ can: boolean }>(
    `SELECT NOT EXISTS (
       SELECT 1 FROM alerts
       WHERE device_eui = $1 AND metric = $2 AND cooldown_until > NOW()
     ) AS can`,
    [deviceEui, metric]
  )
  return result.rows[0]?.can ?? true
}

export async function registerAlert(
  deviceEui: string,
  metric: string,
  value: number,
  threshold: number,
  channel: string,
  cooldownMinutes: number
): Promise<void> {
  await pool.query(
    `INSERT INTO alerts (device_eui, metric, value, threshold, channel, cooldown_until)
     VALUES ($1, $2, $3, $4, $5, NOW() + make_interval(mins => $6))`,
    [deviceEui, metric, value, threshold, channel, cooldownMinutes]
  )
}

export async function listAlerts(
  limit: number,
  offset: number
): Promise<{ rows: AlertRow[]; total: number }> {
  const count = await pool.query<{ count: string }>('SELECT COUNT(*)::text AS count FROM alerts')
  const result = await pool.query<AlertRow>(
    `SELECT id, device_eui, metric, value, threshold, channel, sent_at, cooldown_until
     FROM alerts
     ORDER BY sent_at DESC
     LIMIT $1 OFFSET $2`,
    [limit, offset]
  )
  return { rows: result.rows, total: Number(count.rows[0]?.count ?? 0) }
}
```

- [ ] **Step 4: Typecheck**

Run (from `chirpstack-dashboard/backend`):

```bash
npx tsc --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 5: Commit**

```bash
git add chirpstack-dashboard/backend/src/repositories
git commit -m "feat(backend): repositories de telemetria, dispositivos e alertas"
```

---

## Task 6: PersistService with tests

**Files:**
- Create: `chirpstack-dashboard/backend/src/services/persistService.ts`
- Test: `chirpstack-dashboard/backend/test/persistService.test.ts`

- [ ] **Step 1: Write the failing test**

`chirpstack-dashboard/backend/test/persistService.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { Reading } from '../src/types'

const mocks = vi.hoisted(() => ({
  insertTelemetryBatch: vi.fn(),
  upsertDevices: vi.fn(),
  waitForDb: vi.fn(),
}))

vi.mock('../src/repositories/telemetryRepository', () => ({
  insertTelemetryBatch: mocks.insertTelemetryBatch,
}))
vi.mock('../src/repositories/deviceRepository', () => ({
  upsertDevices: mocks.upsertDevices,
}))
vi.mock('../src/db/pool', () => ({
  waitForDb: mocks.waitForDb,
}))

import { PersistService } from '../src/services/persistService'

const makeReading = (i: number): Reading => ({
  deviceEui: `eui-${i}`,
  deviceName: `dev-${i}`,
  applicationId: 'app',
  metrics: { ldr_value: i },
  timestamp: new Date().toISOString(),
  raw: {},
})

describe('PersistService', () => {
  let service: PersistService

  beforeEach(() => {
    vi.useFakeTimers()
    mocks.insertTelemetryBatch.mockReset()
    mocks.upsertDevices.mockReset()
    mocks.waitForDb.mockResolvedValue(undefined)
    service = new PersistService()
  })

  afterEach(() => {
    service.stop()
    vi.useRealTimers()
  })

  it('grava lote em batch e limpa a fila', async () => {
    service.enqueue(makeReading(1))
    service.enqueue(makeReading(2))
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(1)
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledWith([expect.anything(), expect.anything()])
    expect(mocks.upsertDevices).toHaveBeenCalledWith([expect.anything(), expect.anything()])
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(1)
  })

  it('reenfileira o lote quando a gravação falha', async () => {
    mocks.insertTelemetryBatch.mockRejectedValueOnce(new Error('db down'))
    service.enqueue(makeReading(1))
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(1)
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(2)
  })

  it('descartar a leitura mais antiga quando a fila estoura', () => {
    for (let i = 0; i < 3; i++) service.enqueue(makeReading(i))
    for (let i = 3; i < 6; i++) service.enqueue(makeReading(i))
    expect(service.size()).toBeLessThanOrEqual(5)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `chirpstack-dashboard/backend`):

```bash
npx vitest run test/persistService.test.ts
```

Expected: FAIL — cannot find module `../src/services/persistService`.

- [ ] **Step 3: Write the implementation**

`chirpstack-dashboard/backend/src/services/persistService.ts`:

```ts
import { insertTelemetryBatch } from '../repositories/telemetryRepository'
import { upsertDevices } from '../repositories/deviceRepository'
import { waitForDb } from '../db/pool'
import { env } from '../config/env'
import { logger } from '../utils/logger'
import type { Reading } from '../types'

export class PersistService {
  private queue: Reading[] = []
  private timer: NodeJS.Timeout | null = null
  private flushing = false

  start(): void {
    if (this.timer) return
    this.timer = setInterval(() => void this.flush(), env.PERSIST_FLUSH_MS)
    logger.info(`[persist] Fila iniciada (flush a cada ${env.PERSIST_FLUSH_MS}ms, batch de ${env.PERSIST_BATCH_SIZE})`)
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
  }

  enqueue(reading: Reading): void {
    if (this.queue.length >= env.QUEUE_MAX_SIZE) {
      logger.warn('[persist] Fila cheia, descartando leitura mais antiga')
      this.queue.shift()
    }
    this.queue.push(reading)
  }

  size(): number {
    return this.queue.length
  }

  async flush(): Promise<void> {
    if (this.flushing || this.queue.length === 0) return
    this.flushing = true
    const batch = this.queue.splice(0, env.PERSIST_BATCH_SIZE)
    try {
      await waitForDb()
      await insertTelemetryBatch(batch)
      await upsertDevices(batch)
    } catch (err) {
      logger.error('[persist] Erro ao gravar lote, reenfileirando', err)
      this.queue.unshift(...batch)
    } finally {
      this.flushing = false
    }
  }
}
```

Note: the test calls `service.size()` and `service.stop()` — both exist in the implementation above. The "queue overflow" test enqueues 6 readings while `QUEUE_MAX_SIZE` is the real env value (5000), so `size()` will be 6, not ≤ 5. To make the test deterministic, the third test must control the env. Fix the test to set a small max by setting `process.env.QUEUE_MAX_SIZE` before importing the module (Task 2 pattern). Replace the third test case in `test/persistService.test.ts` with:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { Reading } from '../src/types'

const mocks = vi.hoisted(() => ({
  insertTelemetryBatch: vi.fn(),
  upsertDevices: vi.fn(),
  waitForDb: vi.fn(),
}))

vi.mock('../src/repositories/telemetryRepository', () => ({
  insertTelemetryBatch: mocks.insertTelemetryBatch,
}))
vi.mock('../src/repositories/deviceRepository', () => ({
  upsertDevices: mocks.upsertDevices,
}))
vi.mock('../src/db/pool', () => ({
  waitForDb: mocks.waitForDb,
}))

process.env.QUEUE_MAX_SIZE = '5'

import { PersistService } from '../src/services/persistService'
```

And the third test becomes:

```ts
  it('descartar a leitura mais antiga quando a fila estoura', () => {
    for (let i = 0; i < 7; i++) service.enqueue(makeReading(i))
    expect(service.size()).toBe(5)
    const queue = (service as unknown as { queue: Reading[] }).queue
    expect(queue[0].deviceEui).toBe('eui-2')
    expect(queue[4].deviceEui).toBe('eui-6')
  })
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
npx vitest run test/persistService.test.ts
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add chirpstack-dashboard/backend/src/services/persistService.ts chirpstack-dashboard/backend/test/persistService.test.ts
git commit -m "feat(backend): fila de persistência em batch não-bloqueante"
```

---

## Task 7: LiveService (Socket.io) + MQTT client

**Files:**
- Create: `chirpstack-dashboard/backend/src/services/liveService.ts`
- Create: `chirpstack-dashboard/backend/src/mqtt/client.ts`

- [ ] **Step 1: Create the LiveService**

`chirpstack-dashboard/backend/src/services/liveService.ts`:

```ts
import type { Server } from 'socket.io'
import type { Reading } from '../types'

export interface LiveService {
  emitReading(reading: Reading): void
}

export function setupLiveService(io: Server): LiveService {
  io.on('connection', () => {
    io.emit('server:status', { online: true })
  })
  return {
    emitReading(reading: Reading): void {
      io.emit('telemetry:new', reading)
    },
  }
}
```

- [ ] **Step 2: Create the MQTT client**

`chirpstack-dashboard/backend/src/mqtt/client.ts`:

```ts
import mqtt, { type MqttClient } from 'mqtt'
import { env } from '../config/env'
import { logger } from '../utils/logger'

export function connectMqtt(onMessage: (topic: string, payload: string) => void): MqttClient {
  const client = mqtt.connect(env.MQTT_URL, {
    username: env.MQTT_USERNAME || undefined,
    password: env.MQTT_PASSWORD || undefined,
    reconnectPeriod: 3000,
    connectTimeout: 10000,
  })

  client.on('connect', () => {
    logger.info(`[mqtt] Conectado a ${env.MQTT_URL}`)
    client.subscribe(env.MQTT_TOPIC, (err) => {
      if (err) logger.error(`[mqtt] Falha ao subscrever ${env.MQTT_TOPIC}`, err)
      else logger.info(`[mqtt] Assinando tópico ${env.MQTT_TOPIC}`)
    })
  })
  client.on('reconnect', () => logger.info('[mqtt] Reconectando...'))
  client.on('offline', () => logger.warn('[mqtt] Offline'))
  client.on('error', (err) => logger.error('[mqtt] Erro', err))
  client.on('message', (topic, payload) => onMessage(topic, payload.toString()))

  return client
}
```

- [ ] **Step 3: Typecheck**

Run (from `chirpstack-dashboard/backend`):

```bash
npx tsc --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 4: Commit**

```bash
git add chirpstack-dashboard/backend/src/services/liveService.ts chirpstack-dashboard/backend/src/mqtt/client.ts
git commit -m "feat(backend): broadcast socket.io e cliente mqtt com reconexão"
```

---

## Task 8: Threshold rules + engine with tests

**Files:**
- Create: `chirpstack-dashboard/backend/src/services/rules.ts`
- Create: `chirpstack-dashboard/backend/src/services/thresholdEngine.ts`
- Test: `chirpstack-dashboard/backend/test/rules.test.ts`
- Test: `chirpstack-dashboard/backend/test/thresholdEngine.test.ts`

- [ ] **Step 1: Write the failing rules test**

`chirpstack-dashboard/backend/test/rules.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { parseRules, evaluateRule } from '../src/services/rules'

describe('parseRules', () => {
  it('parseia múltiplas regras no formato metrica:operador:valor', () => {
    const rules = parseRules('ldr_value:>:500;temperature:>:35;battery_level:<:3.2')
    expect(rules).toEqual([
      { metric: 'ldr_value', operator: '>', value: 500 },
      { metric: 'temperature', operator: '>', value: 35 },
      { metric: 'battery_level', operator: '<', value: 3.2 },
    ])
  })

  it('ignora partes vazias e espaços', () => {
    const rules = parseRules('  ldr_value:>:100 ;  ; temperature:>=:40  ')
    expect(rules).toHaveLength(2)
    expect(rules[1].operator).toBe('>=')
  })

  it('lança erro para regra malformada', () => {
    expect(() => parseRules('ldr_value:>')).toThrow(/Regra inválida/)
  })

  it('retorna lista vazia para string vazia', () => {
    expect(parseRules('')).toEqual([])
  })
})

describe('evaluateRule', () => {
  const cases: Array<[string, number, number, boolean]> = [
    ['>', 501, 500, true],
    ['>', 500, 500, false],
    ['>=', 500, 500, true],
    ['<', 3.1, 3.2, true],
    ['<', 3.3, 3.2, false],
    ['<=', 3.2, 3.2, true],
  ]
  it.each(cases)('operador %s: valor %d vs limite %d → %s', (op, value, threshold, expected) => {
    expect(evaluateRule({ metric: 'm', operator: op as never, value: threshold }, value)).toBe(expected)
  })
})
```

- [ ] **Step 2: Write the failing engine test**

`chirpstack-dashboard/backend/test/thresholdEngine.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Reading } from '../src/types'

const mocks = vi.hoisted(() => ({
  canAlert: vi.fn(),
  registerAlert: vi.fn(),
}))

vi.mock('../src/repositories/alertRepository', () => ({
  canAlert: mocks.canAlert,
  registerAlert: mocks.registerAlert,
}))

process.env.THRESHOLD_RULES = 'ldr_value:>:500;battery_level:<:3.2'
process.env.ALERT_COOLDOWN_MINUTES = '5'

import { ThresholdEngine } from '../src/services/thresholdEngine'

const makeReading = (metrics: Record<string, number>): Reading => ({
  deviceEui: 'eui-1',
  deviceName: 'esp-1',
  applicationId: 'app',
  metrics,
  timestamp: '2026-07-30T12:00:00Z',
  raw: {},
})

describe('ThresholdEngine', () => {
  let sender: { send: ReturnType<typeof vi.fn> }

  beforeEach(() => {
    sender = { send: vi.fn().mockResolvedValue(undefined) }
    mocks.canAlert.mockReset()
    mocks.registerAlert.mockReset()
    mocks.canAlert.mockResolvedValue(true)
    mocks.registerAlert.mockResolvedValue(undefined)
  })

  it('dispara alerta quando a métrica ultrapassa o limite', async () => {
    const engine = new ThresholdEngine(sender)
    await engine.process(makeReading({ ldr_value: 600, battery_level: 3.9 }))
    expect(sender.send).toHaveBeenCalledTimes(1)
    expect(sender.send).toHaveBeenCalledWith(
      expect.objectContaining({ metric: 'ldr_value', value: 600, threshold: 500 })
    )
    expect(mocks.registerAlert).toHaveBeenCalledWith(
      'eui-1', 'ldr_value', 600, 500, expect.any(String), 5
    )
  })

  it('não dispara quando nenhuma regra é violada', async () => {
    const engine = new ThresholdEngine(sender)
    await engine.process(makeReading({ ldr_value: 100, battery_level: 3.9 }))
    expect(sender.send).not.toHaveBeenCalled()
  })

  it('respeita o cooldown (canAlert falso → sem envio)', async () => {
    mocks.canAlert.mockResolvedValue(false)
    const engine = new ThresholdEngine(sender)
    await engine.process(makeReading({ ldr_value: 900 }))
    expect(sender.send).not.toHaveBeenCalled()
    expect(mocks.registerAlert).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run both tests to verify they fail**

Run (from `chirpstack-dashboard/backend`):

```bash
npx vitest run test/rules.test.ts test/thresholdEngine.test.ts
```

Expected: FAIL — cannot find modules `../src/services/rules` and `../src/services/thresholdEngine`.

- [ ] **Step 4: Write the rules implementation**

`chirpstack-dashboard/backend/src/services/rules.ts`:

```ts
import type { ThresholdOperator } from '../types'

export interface ThresholdRule {
  metric: string
  operator: ThresholdOperator
  value: number
}

const RULE_PATTERN = /^([A-Za-z0-9_]+)(>=|<=|>|<)(-?\d+(?:\.\d+)?)$/

export function parseRules(raw: string): ThresholdRule[] {
  const rules: ThresholdRule[] = []
  for (const part of raw.split(';')) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const match = RULE_PATTERN.exec(trimmed)
    if (!match) {
      throw new Error(`Regra inválida: "${trimmed}" (esperado metrica:operador:valor, ex.: ldr_value:>:500)`)
    }
    rules.push({ metric: match[1], operator: match[2] as ThresholdOperator, value: Number(match[3]) })
  }
  return rules
}

export function evaluateRule(rule: ThresholdRule, value: number): boolean {
  switch (rule.operator) {
    case '>':
      return value > rule.value
    case '<':
      return value < rule.value
    case '>=':
      return value >= rule.value
    case '<=':
      return value <= rule.value
  }
}
```

- [ ] **Step 5: Write the engine implementation**

`chirpstack-dashboard/backend/src/services/thresholdEngine.ts`:

```ts
import { canAlert, registerAlert } from '../repositories/alertRepository'
import { env } from '../config/env'
import { parseRules, evaluateRule, type ThresholdRule } from './rules'
import { logger } from '../utils/logger'
import type { AlertEvent, AlertSender, Reading } from '../types'

export class ThresholdEngine {
  private rules: ThresholdRule[] = []

  constructor(private readonly sender: AlertSender) {
    this.reload()
  }

  reload(): void {
    this.rules = parseRules(env.THRESHOLD_RULES)
  }

  async process(reading: Reading): Promise<void> {
    if (this.rules.length === 0) return
    for (const rule of this.rules) {
      const value = reading.metrics[rule.metric]
      if (value === undefined) continue
      if (!evaluateRule(rule, value)) continue
      if (!(await canAlert(reading.deviceEui, rule.metric))) continue
      await registerAlert(
        reading.deviceEui,
        rule.metric,
        value,
        rule.value,
        'all',
        env.ALERT_COOLDOWN_MINUTES
      )
      const event: AlertEvent = {
        deviceEui: reading.deviceEui,
        deviceName: reading.deviceName,
        metric: rule.metric,
        value,
        threshold: rule.value,
        operator: rule.operator,
        timestamp: reading.timestamp,
      }
      await this.sender.send(event)
      logger.warn(
        `[alerts] ${reading.deviceName} (${reading.deviceEui}): ${rule.metric} = ${value} ${rule.operator} ${rule.value}`
      )
    }
  }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
npx vitest run test/rules.test.ts test/thresholdEngine.test.ts
```

Expected: PASS (rules: 4, engine: 3).

- [ ] **Step 7: Commit**

```bash
git add chirpstack-dashboard/backend/src/services/rules.ts chirpstack-dashboard/backend/src/services/thresholdEngine.ts chirpstack-dashboard/backend/test/rules.test.ts chirpstack-dashboard/backend/test/thresholdEngine.test.ts
git commit -m "feat(backend): motor de thresholds com cooldown por device+métrica"
```

---

## Task 9: Alert notifiers (Telegram + Email + factory)

**Files:**
- Create: `chirpstack-dashboard/backend/src/alerts/telegramNotifier.ts`
- Create: `chirpstack-dashboard/backend/src/alerts/emailNotifier.ts`
- Create: `chirpstack-dashboard/backend/src/alerts/index.ts`

- [ ] **Step 1: Create the Telegram notifier**

`chirpstack-dashboard/backend/src/alerts/telegramNotifier.ts`:

```ts
import type { AlertEvent } from '../types'

export async function sendTelegramAlert(
  token: string,
  chatId: string,
  event: AlertEvent
): Promise<void> {
  const text = [
    '🚨 ALERTA LoRaWAN',
    `Device: ${event.deviceName} (${event.deviceEui})`,
    `Métrica: ${event.metric}`,
    `Valor: ${event.value} ${event.operator} ${event.threshold}`,
    `Horário: ${event.timestamp}`,
  ].join('\n')

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  })
  if (!res.ok) {
    throw new Error(`Telegram HTTP ${res.status}: ${await res.text()}`)
  }
}
```

- [ ] **Step 2: Create the Email notifier**

`chirpstack-dashboard/backend/src/alerts/emailNotifier.ts`:

```ts
import nodemailer from 'nodemailer'
import { env } from '../config/env'
import type { AlertEvent } from '../types'

export async function sendEmailAlert(event: AlertEvent): Promise<void> {
  const transporter = nodemailer.createTransport({
    host: env.SMTP_HOST,
    port: env.SMTP_PORT,
    secure: env.SMTP_SECURE,
    auth:
      env.SMTP_USER && env.SMTP_PASS
        ? { user: env.SMTP_USER, pass: env.SMTP_PASS }
        : undefined,
  })

  await transporter.sendMail({
    from: env.ALERT_EMAIL_FROM,
    to: env.ALERT_EMAIL_TO,
    subject: `[LoRaWAN] Alerta: ${event.metric} ${event.operator} ${event.threshold}`,
    html: `
      <h2>🚨 Alerta LoRaWAN</h2>
      <table border="1" cellpadding="8" style="border-collapse: collapse">
        <tr><td><b>Device</b></td><td>${event.deviceName} (${event.deviceEui})</td></tr>
        <tr><td><b>Métrica</b></td><td>${event.metric}</td></tr>
        <tr><td><b>Valor</b></td><td>${event.value}</td></tr>
        <tr><td><b>Limite</b></td><td>${event.operator} ${event.threshold}</td></tr>
        <tr><td><b>Horário</b></td><td>${event.timestamp}</td></tr>
      </table>
    `,
  })
}
```

- [ ] **Step 3: Create the notifier factory**

`chirpstack-dashboard/backend/src/alerts/index.ts`:

```ts
import { env } from '../config/env'
import { logger } from '../utils/logger'
import { sendTelegramAlert } from './telegramNotifier'
import { sendEmailAlert } from './emailNotifier'
import type { AlertEvent, AlertSender } from '../types'

export function createAlertSender(): AlertSender {
  const channels: Array<(event: AlertEvent) => Promise<void>> = []

  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    channels.push((event) => sendTelegramAlert(env.TELEGRAM_BOT_TOKEN!, env.TELEGRAM_CHAT_ID!, event))
    logger.info('[alerts] Canal Telegram ativo')
  }
  if (env.SMTP_HOST && env.ALERT_EMAIL_FROM && env.ALERT_EMAIL_TO) {
    channels.push(sendEmailAlert)
    logger.info('[alerts] Canal E-mail ativo')
  }
  if (channels.length === 0) {
    logger.warn('[alerts] Nenhum canal configurado — alertas apenas registrados no banco')
  }

  return {
    async send(event: AlertEvent): Promise<void> {
      await Promise.allSettled(channels.map((channel) => channel(event)))
    },
  }
}
```

- [ ] **Step 4: Typecheck**

Run (from `chirpstack-dashboard/backend`):

```bash
npx tsc --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 5: Commit**

```bash
git add chirpstack-dashboard/backend/src/alerts
git commit -m "feat(backend): notificadores telegram e e-mail com factory por env"
```

---

## Task 10: REST routes + index.ts wiring

**Files:**
- Create: `chirpstack-dashboard/backend/src/routes/health.ts`
- Create: `chirpstack-dashboard/backend/src/routes/telemetry.ts`
- Create: `chirpstack-dashboard/backend/src/routes/devices.ts`
- Create: `chirpstack-dashboard/backend/src/routes/alerts.ts`
- Create: `chirpstack-dashboard/backend/src/index.ts`

- [ ] **Step 1: Create the health route**

`chirpstack-dashboard/backend/src/routes/health.ts`:

```ts
import { Router } from 'express'
import { pool } from '../db/pool'

export const healthRouter = Router()

healthRouter.get('/', async (_req, res) => {
  let dbOk = false
  try {
    await pool.query('SELECT 1')
    dbOk = true
  } catch {
    dbOk = false
  }
  res.json({ status: 'ok', db: dbOk ? 'up' : 'down', uptime: process.uptime() })
})
```

- [ ] **Step 2: Create the telemetry route**

`chirpstack-dashboard/backend/src/routes/telemetry.ts`:

```ts
import { Router } from 'express'
import { queryTelemetry } from '../repositories/telemetryRepository'

export const telemetryRouter = Router()

telemetryRouter.get('/', async (req, res, next) => {
  try {
    const limit = Math.min(Math.max(Number(req.query.limit) || 50, 1), 500)
    const offset = Math.max(Number(req.query.offset) || 0, 0)
    const deviceEui = typeof req.query.device_eui === 'string' ? req.query.device_eui : undefined
    const from = typeof req.query.from === 'string' ? req.query.from : undefined
    const to = typeof req.query.to === 'string' ? req.query.to : undefined
    const { rows, total } = await queryTelemetry({ deviceEui, from, to, limit, offset })
    res.json({ rows, total, limit, offset })
  } catch (err) {
    next(err)
  }
})
```

- [ ] **Step 3: Create the devices route**

`chirpstack-dashboard/backend/src/routes/devices.ts`:

```ts
import { Router } from 'express'
import { listDevices } from '../repositories/deviceRepository'
import { env } from '../config/env'

export const devicesRouter = Router()

devicesRouter.get('/', async (_req, res, next) => {
  try {
    const devices = await listDevices(env.OFFLINE_THRESHOLD_MINUTES)
    res.json({ devices })
  } catch (err) {
    next(err)
  }
})
```

- [ ] **Step 4: Create the alerts route**

`chirpstack-dashboard/backend/src/routes/alerts.ts`:

```ts
import { Router } from 'express'
import { listAlerts } from '../repositories/alertRepository'

export const alertsRouter = Router()

alertsRouter.get('/', async (req, res, next) => {
  try {
    const limit = Math.min(Math.max(Number(req.query.limit) || 20, 1), 200)
    const offset = Math.max(Number(req.query.offset) || 0, 0)
    const { rows, total } = await listAlerts(limit, offset)
    res.json({ rows, total, limit, offset })
  } catch (err) {
    next(err)
  }
})
```

- [ ] **Step 5: Create the index.ts**

`chirpstack-dashboard/backend/src/index.ts`:

```ts
import http from 'node:http'
import express from 'express'
import cors from 'cors'
import { Server } from 'socket.io'
import { env } from './config/env'
import { logger } from './utils/logger'
import { waitForDb } from './db/pool'
import { migrate } from './db/migrate'
import { connectMqtt } from './mqtt/client'
import { parseUplink } from './mqtt/parser'
import { PersistService } from './services/persistService'
import { setupLiveService } from './services/liveService'
import { ThresholdEngine } from './services/thresholdEngine'
import { createAlertSender } from './alerts'
import { healthRouter } from './routes/health'
import { telemetryRouter } from './routes/telemetry'
import { devicesRouter } from './routes/devices'
import { alertsRouter } from './routes/alerts'

async function main(): Promise<void> {
  await waitForDb()
  await migrate()

  const app = express()
  app.use(express.json())
  if (env.CORS_ORIGIN) app.use(cors({ origin: env.CORS_ORIGIN }))

  app.use('/api/health', healthRouter)
  app.use('/api/telemetry', telemetryRouter)
  app.use('/api/devices', devicesRouter)
  app.use('/api/alerts', alertsRouter)

  const server = http.createServer(app)
  const io = new Server(server, {
    cors: { origin: env.CORS_ORIGIN ?? true },
  })
  const live = setupLiveService(io)

  const persist = new PersistService()
  persist.start()

  const sender = createAlertSender()
  const engine = new ThresholdEngine(sender)

  connectMqtt((topic, payload) => {
    const reading = parseUplink(payload)
    if (!reading) {
      logger.warn(`[mqtt] Payload inválido descartado (tópico ${topic})`)
      return
    }
    persist.enqueue(reading)
    live.emitReading(reading)
    void engine.process(reading).catch((err) => logger.error('[alerts] Falha ao processar regras', err))
  })

  server.listen(env.PORT, () => {
    logger.info(`[http] Dashboard backend em http://0.0.0.0:${env.PORT}`)
  })
}

main().catch((err) => {
  logger.error('[fatal] Falha ao iniciar backend', err)
  process.exit(1)
})
```

- [ ] **Step 6: Typecheck + build**

Run (from `chirpstack-dashboard/backend`):

```bash
npm run typecheck && npm run build
```

Expected: both exit 0, `dist/index.js` produced.

- [ ] **Step 7: Commit**

```bash
git add chirpstack-dashboard/backend/src/routes chirpstack-dashboard/backend/src/index.ts
git commit -m "feat(backend): rotas REST e orquestração (index.ts) com socket.io + mqtt"
```

---

## Task 11: Backend Dockerfile

**Files:**
- Create: `chirpstack-dashboard/backend/Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

`chirpstack-dashboard/backend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
EXPOSE 4000
CMD ["node", "dist/index.js"]
```

- [ ] **Step 2: Build the image to verify**

Run (from `chirpstack-dashboard/backend`):

```bash
docker build -t chirpstack-dashboard-backend:test .
```

Expected: build succeeds and finishes with `docker` success message.

- [ ] **Step 3: Commit**

```bash
git add chirpstack-dashboard/backend/Dockerfile
git commit -m "feat(backend): Dockerfile multi-stage de produção"
```

---

## Task 12: Scaffold frontend (Vite + React + TS + Tailwind)

**Files:**
- Create: `chirpstack-dashboard/frontend/package.json`
- Create: `chirpstack-dashboard/frontend/tsconfig.json`
- Create: `chirpstack-dashboard/frontend/vite.config.ts`
- Create: `chirpstack-dashboard/frontend/tailwind.config.js`
- Create: `chirpstack-dashboard/frontend/postcss.config.js`
- Create: `chirpstack-dashboard/frontend/index.html`
- Create: `chirpstack-dashboard/frontend/src/main.tsx`
- Create: `chirpstack-dashboard/frontend/src/index.css`
- Create: `chirpstack-dashboard/frontend/.dockerignore`

- [ ] **Step 1: Create the package.json**

`chirpstack-dashboard/frontend/package.json`:

```json
{
  "name": "chirpstack-dashboard-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.12.7",
    "socket.io-client": "^4.7.5"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.39",
    "tailwindcss": "^3.4.6",
    "typescript": "^5.5.0",
    "vite": "^5.3.3"
  }
}
```

- [ ] **Step 2: Create the tsconfig.json**

`chirpstack-dashboard/frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create the vite config**

`chirpstack-dashboard/frontend/vite.config.ts`:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:4000', changeOrigin: true },
      '/socket.io': { target: 'http://localhost:4000', ws: true, changeOrigin: true },
    },
  },
})
```

- [ ] **Step 4: Create Tailwind and PostCSS configs**

`chirpstack-dashboard/frontend/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

`chirpstack-dashboard/frontend/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 5: Create index.html**

`chirpstack-dashboard/frontend/index.html`:

```html
<!doctype html>
<html lang="pt-BR" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ChirpStack Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create main.tsx and index.css**

`chirpstack-dashboard/frontend/src/main.tsx`:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

`chirpstack-dashboard/frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light;
}
.dark {
  color-scheme: dark;
}
```

- [ ] **Step 7: Create the .dockerignore**

`chirpstack-dashboard/frontend/.dockerignore`:

```
node_modules
dist
.env
```

- [ ] **Step 8: Install and build-verify**

Run (from `chirpstack-dashboard/frontend`):

```bash
npm install
```

Expected: install completes. Note: build will fail at this point because `src/App.tsx` does not exist yet — that's expected. Continue to Task 13.

- [ ] **Step 9: Commit**

```bash
git add chirpstack-dashboard/frontend
git commit -m "chore(frontend): scaffold Vite + React + TS + Tailwind"
```

---

## Task 13: Frontend types, API client, socket, hook

**Files:**
- Create: `chirpstack-dashboard/frontend/src/types.ts`
- Create: `chirpstack-dashboard/frontend/src/api/client.ts`
- Create: `chirpstack-dashboard/frontend/src/socket/socket.ts`
- Create: `chirpstack-dashboard/frontend/src/hooks/useTelemetrySocket.ts`

- [ ] **Step 1: Create the types**

`chirpstack-dashboard/frontend/src/types.ts`:

```ts
export interface Reading {
  deviceEui: string
  deviceName: string
  applicationId: string
  fCnt?: number
  rssi?: number
  snr?: number
  metrics: Record<string, number>
  timestamp: string
}

export interface DeviceStatus {
  device_eui: string
  device_name: string
  application_id: string
  last_seen_at: string
  last_rssi: number | null
  last_snr: number | null
  created_at: string
  online: boolean
}

export interface TelemetryRow {
  id: number
  device_eui: string
  device_name: string
  application_id: string
  temperature: number | null
  humidity: number | null
  battery_level: number | null
  rssi: number | null
  snr: number | null
  fcnt: number | null
  payload: unknown
  timestamp: string
}

export interface AlertRow {
  id: number
  device_eui: string
  metric: string
  value: number
  threshold: number
  channel: string
  sent_at: string
  cooldown_until: string
}

export interface TelemetryResponse {
  rows: TelemetryRow[]
  total: number
  limit: number
  offset: number
}

export interface DevicesResponse {
  devices: DeviceStatus[]
}

export interface AlertsResponse {
  rows: AlertRow[]
  total: number
  limit: number
  offset: number
}
```

- [ ] **Step 2: Create the API client**

`chirpstack-dashboard/frontend/src/api/client.ts`:

```ts
import type { AlertsResponse, DevicesResponse, TelemetryResponse } from '../types'

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export interface TelemetryParams {
  deviceEui?: string
  from?: string
  to?: string
  limit: number
  offset: number
}

export const api = {
  telemetry(params: TelemetryParams): Promise<TelemetryResponse> {
    const q = new URLSearchParams()
    if (params.deviceEui) q.set('device_eui', params.deviceEui)
    if (params.from) q.set('from', params.from)
    if (params.to) q.set('to', params.to)
    q.set('limit', String(params.limit))
    q.set('offset', String(params.offset))
    return get<TelemetryResponse>(`/api/telemetry?${q.toString()}`)
  },
  devices(): Promise<DevicesResponse> {
    return get<DevicesResponse>('/api/devices')
  },
  alerts(limit = 20): Promise<AlertsResponse> {
    return get<AlertsResponse>(`/api/alerts?limit=${limit}`)
  },
}
```

- [ ] **Step 3: Create the socket module**

`chirpstack-dashboard/frontend/src/socket/socket.ts`:

```ts
import { io, type Socket } from 'socket.io-client'

let socket: Socket | null = null

export function connectSocket(): Socket {
  if (socket) return socket
  socket = io()
  return socket
}
```

- [ ] **Step 4: Create the hook**

`chirpstack-dashboard/frontend/src/hooks/useTelemetrySocket.ts`:

```ts
import { useEffect, useState } from 'react'
import type { Reading } from '../types'
import { connectSocket } from '../socket/socket'

const BUFFER_SIZE = 60

export function useTelemetrySocket() {
  const [connected, setConnected] = useState(false)
  const [buffer, setBuffer] = useState<Record<string, Reading[]>>({})

  useEffect(() => {
    const socket = connectSocket()
    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))
    socket.on('telemetry:new', (reading: Reading) => {
      setBuffer((prev) => {
        const arr = prev[reading.deviceEui] ?? []
        const next = [...arr, reading]
        if (next.length > BUFFER_SIZE) next.splice(0, next.length - BUFFER_SIZE)
        return { ...prev, [reading.deviceEui]: next }
      })
    })
    return () => {
      socket.off('connect')
      socket.off('disconnect')
      socket.off('telemetry:new')
    }
  }, [])

  return { connected, buffer }
}
```

- [ ] **Step 5: Typecheck**

Run (from `chirpstack-dashboard/frontend`):

```bash
npx tsc --noEmit
```

Expected: exits 0 with no output.

- [ ] **Step 6: Commit**

```bash
git add chirpstack-dashboard/frontend/src/types.ts chirpstack-dashboard/frontend/src/api chirpstack-dashboard/frontend/src/socket chirpstack-dashboard/frontend/src/hooks
git commit -m "feat(frontend): tipos, api client, socket e hook de tempo real"
```

---

## Task 14: Frontend components + App

**Files:**
- Create: `chirpstack-dashboard/frontend/src/components/Header.tsx`
- Create: `chirpstack-dashboard/frontend/src/components/MetricCard.tsx`
- Create: `chirpstack-dashboard/frontend/src/components/DeviceCards.tsx`
- Create: `chirpstack-dashboard/frontend/src/components/RealtimeChart.tsx`
- Create: `chirpstack-dashboard/frontend/src/components/HistoryTable.tsx`
- Create: `chirpstack-dashboard/frontend/src/components/AlertsPanel.tsx`
- Create: `chirpstack-dashboard/frontend/src/App.tsx`

- [ ] **Step 1: Create the Header**

`chirpstack-dashboard/frontend/src/components/Header.tsx`:

```tsx
interface HeaderProps {
  connected: boolean
  dark: boolean
  onToggleTheme: () => void
}

export function Header({ connected, dark, onToggleTheme }: HeaderProps) {
  return (
    <header className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">ChirpStack Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Telemetria LoRaWAN em tempo real</p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
              connected
                ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            {connected ? 'Conectado' : 'Desconectado'}
          </span>
          <button
            onClick={onToggleTheme}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200"
          >
            {dark ? '☀️ Claro' : '🌙 Escuro'}
          </button>
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 2: Create the MetricCard**

`chirpstack-dashboard/frontend/src/components/MetricCard.tsx`:

```tsx
interface MetricCardProps {
  label: string
  value: string
  unit?: string
}

export function MetricCard({ label, value, unit }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-gray-500 dark:text-gray-400">{unit}</span>}
      </p>
    </div>
  )
}
```

- [ ] **Step 3: Create the DeviceCards**

`chirpstack-dashboard/frontend/src/components/DeviceCards.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { DeviceStatus, Reading } from '../types'

interface DeviceCardsProps {
  buffer: Record<string, Reading[]>
  selectedDevice?: string
  onSelect: (eui: string) => void
}

const fmtTime = (iso: string): string =>
  new Date(iso).toLocaleString('pt-BR', { hour12: false })

export function DeviceCards({ buffer, selectedDevice, onSelect }: DeviceCardsProps) {
  const [devices, setDevices] = useState<DeviceStatus[]>([])

  useEffect(() => {
    api
      .devices()
      .then((r) => setDevices(r.devices))
      .catch(() => {})
  }, [])

  const allEuis = Array.from(new Set([...devices.map((d) => d.device_eui), ...Object.keys(buffer)]))

  if (allEuis.length === 0) {
    return (
      <div className="rounded-xl border-2 border-dashed border-gray-300 p-10 text-center text-gray-500 dark:border-gray-700 dark:text-gray-400">
        Aguardando primeiro uplink do dispositivo...
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {allEuis.map((eui) => {
        const device = devices.find((d) => d.device_eui === eui)
        const readings = buffer[eui] ?? []
        const reading = readings[readings.length - 1]
        const online = device ? device.online : Boolean(reading)
        const active = selectedDevice === eui

        return (
          <button
            key={eui}
            onClick={() => onSelect(eui)}
            className={`rounded-xl border p-4 text-left shadow-sm transition-colors ${
              active
                ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-900/20'
                : 'border-gray-200 bg-white hover:border-blue-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-500'
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">{device?.device_name ?? reading?.deviceName ?? eui}</p>
                <p className="font-mono text-xs text-gray-500 dark:text-gray-400">{eui}</p>
              </div>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                  online
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                    : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
                {online ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">LDR</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.metrics.ldr_value?.toFixed(0) ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Bateria</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.metrics.battery_level?.toFixed(2) ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">RSSI</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.rssi != null ? `${reading.rssi} dBm` : '—'}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">SNR</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.snr != null ? `${reading.snr} dB` : '—'}
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
              {reading ? fmtTime(reading.timestamp) : device ? fmtTime(device.last_seen_at) : '—'}
            </p>
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Create the RealtimeChart**

`chirpstack-dashboard/frontend/src/components/RealtimeChart.tsx`:

```tsx
import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Reading } from '../types'

const METRICS: Array<{ key: string; label: string }> = [
  { key: 'ldr_value', label: 'Luminosidade' },
  { key: 'temperature', label: 'Temperatura' },
  { key: 'humidity', label: 'Umidade' },
  { key: 'battery_level', label: 'Bateria' },
  { key: 'rssi', label: 'RSSI' },
  { key: 'snr', label: 'SNR' },
]

interface RealtimeChartProps {
  data: Reading[]
}

export function RealtimeChart({ data }: RealtimeChartProps) {
  const [metric, setMetric] = useState('ldr_value')

  const chartData = data.map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString('pt-BR', { hour12: false }),
    value:
      r.metrics[metric] ??
      (metric === 'rssi' ? r.rssi : metric === 'snr' ? r.snr : undefined),
  }))

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-white">Telemetria em tempo real</h2>
        <div className="flex flex-wrap gap-2">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                metric === m.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="time" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '8px',
              color: '#f9fafb',
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="value" name={metric} stroke="#3b82f6" dot={false} />
        </LineChart>
      </ResponsiveContainer>
      {data.length === 0 && (
        <p className="mt-2 text-center text-sm text-gray-500 dark:text-gray-400">
          Sem dados ainda — aguardando uplinks via WebSocket...
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Create the HistoryTable**

`chirpstack-dashboard/frontend/src/components/HistoryTable.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TelemetryRow } from '../types'

const PAGE_SIZE = 20

const fmtTime = (iso: string): string =>
  new Date(iso).toLocaleString('pt-BR', { hour12: false })

export function HistoryTable() {
  const [rows, setRows] = useState<TelemetryRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api
      .telemetry({ deviceEui: search || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => {
        setRows(r.rows)
        setTotal(r.total)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [page, search])

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-white">Histórico</h2>
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(0)
          }}
          placeholder="Buscar por device EUI..."
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 outline-none focus:border-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-700 dark:text-gray-400">
              <th className="px-3 py-2">Horário</th>
              <th className="px-3 py-2">Device</th>
              <th className="px-3 py-2">LDR</th>
              <th className="px-3 py-2">Bateria</th>
              <th className="px-3 py-2">RSSI</th>
              <th className="px-3 py-2">SNR</th>
              <th className="px-3 py-2">FCnt</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-gray-100 text-gray-700 dark:border-gray-800 dark:text-gray-300"
              >
                <td className="px-3 py-2 whitespace-nowrap">{fmtTime(row.timestamp)}</td>
                <td className="px-3 py-2">
                  <span className="font-medium text-gray-900 dark:text-white">{row.device_name}</span>
                  <span className="ml-1 font-mono text-xs text-gray-500">{row.device_eui}</span>
                </td>
                <td className="px-3 py-2">{row.payload ? (row.payload as { object?: { ldr_value?: number } }).object?.ldr_value ?? '—' : '—'}</td>
                <td className="px-3 py-2">{row.battery_level?.toFixed(2) ?? '—'}</td>
                <td className="px-3 py-2">{row.rssi ?? '—'}</td>
                <td className="px-3 py-2">{row.snr ?? '—'}</td>
                <td className="px-3 py-2">{row.fcnt ?? '—'}</td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-gray-500">
                  Nenhum registro encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {total} registro(s) · página {page + 1}/{pages}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-lg border border-gray-300 px-3 py-1 text-sm disabled:opacity-40 dark:border-gray-600"
          >
            Anterior
          </button>
          <button
            onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            disabled={page >= pages - 1}
            className="rounded-lg border border-gray-300 px-3 py-1 text-sm disabled:opacity-40 dark:border-gray-600"
          >
            Próxima
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Create the AlertsPanel**

`chirpstack-dashboard/frontend/src/components/AlertsPanel.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AlertRow } from '../types'

const fmtTime = (iso: string): string =>
  new Date(iso).toLocaleString('pt-BR', { hour12: false })

export function AlertsPanel() {
  const [alerts, setAlerts] = useState<AlertRow[]>([])

  useEffect(() => {
    api
      .alerts(10)
      .then((r) => setAlerts(r.rows))
      .catch(() => {})
  }, [])

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-3 font-semibold text-gray-900 dark:text-white">Alertas recentes</h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Nenhum alerta registrado.</p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((a) => (
            <li
              key={a.id}
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
            >
              <span className="font-semibold">{a.device_eui}</span> · {a.metric} = {a.value}{' '}
              (limite {a.metric} {a.threshold}) · {fmtTime(a.sent_at)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Create App.tsx**

`chirpstack-dashboard/frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Header } from './components/Header'
import { DeviceCards } from './components/DeviceCards'
import { RealtimeChart } from './components/RealtimeChart'
import { AlertsPanel } from './components/AlertsPanel'
import { HistoryTable } from './components/HistoryTable'
import { useTelemetrySocket } from './hooks/useTelemetrySocket'

export default function App() {
  const { connected, buffer } = useTelemetrySocket()
  const [dark, setDark] = useState(true)
  const [selectedDevice, setSelectedDevice] = useState<string | undefined>()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  const deviceEuis = Object.keys(buffer)
  const activeEui =
    selectedDevice && buffer[selectedDevice] ? selectedDevice : deviceEuis[0]
  const chartData = activeEui ? buffer[activeEui] ?? [] : []

  return (
    <div className="min-h-screen bg-gray-100 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      <Header connected={connected} dark={dark} onToggleTheme={() => setDark((d) => !d)} />
      <main className="mx-auto max-w-7xl space-y-6 p-6">
        <DeviceCards buffer={buffer} selectedDevice={selectedDevice} onSelect={setSelectedDevice} />
        <RealtimeChart data={chartData} />
        <AlertsPanel />
        <HistoryTable />
      </main>
    </div>
  )
}
```

- [ ] **Step 8: Typecheck + build**

Run (from `chirpstack-dashboard/frontend`):

```bash
npm run typecheck && npm run build
```

Expected: both exit 0; `dist/` produced with `index.html`.

- [ ] **Step 9: Commit**

```bash
git add chirpstack-dashboard/frontend/src
git commit -m "feat(frontend): componentes do dashboard (cards, gráfico real-time, histórico, alertas)"
```

---

## Task 15: Frontend Dockerfile + nginx

**Files:**
- Create: `chirpstack-dashboard/frontend/Dockerfile`
- Create: `chirpstack-dashboard/frontend/nginx.conf`

- [ ] **Step 1: Create the nginx.conf**

`chirpstack-dashboard/frontend/nginx.conf`:

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://backend:4000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location /socket.io/ {
    proxy_pass http://backend:4000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

- [ ] **Step 2: Create the Dockerfile**

`chirpstack-dashboard/frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 3: Build the image to verify**

Run (from `chirpstack-dashboard/frontend`):

```bash
docker build -t chirpstack-dashboard-frontend:test .
```

Expected: build succeeds and finishes with `docker` success message.

- [ ] **Step 4: Commit**

```bash
git add chirpstack-dashboard/frontend/Dockerfile chirpstack-dashboard/frontend/nginx.conf
git commit -m "feat(frontend): Dockerfile multi-stage com nginx e proxy para o backend"
```

---

## Task 16: Docker Compose + .env.example + .gitignore + README

**Files:**
- Create: `chirpstack-dashboard/docker-compose.yml`
- Create: `chirpstack-dashboard/.env.example`
- Create: `chirpstack-dashboard/.gitignore`

- [ ] **Step 1: Create the .env.example**

`chirpstack-dashboard/.env.example`:

```bash
# --- Backend ---
PORT=4000

# Broker MQTT do ChirpStack. Com `extra_hosts: host-gateway` no compose,
# host.docker.internal resolve o host. Se o dashboard estiver na mesma rede
# docker do chirpstack, use mqtt://mosquitto:1883.
MQTT_URL=mqtt://host.docker.internal:1883
MQTT_TOPIC=application/+/device/+/event/up
MQTT_USERNAME=
MQTT_PASSWORD=

# --- Banco (sobrescrito pelo compose com o host `postgres`) ---
DATABASE_URL=postgres://dashboard:dashboard@postgres:5432/dashboard
DB_POOL_MAX=10

# --- Persistência ---
PERSIST_FLUSH_MS=1000
PERSIST_BATCH_SIZE=200
QUEUE_MAX_SIZE=5000

# --- Status Online/Offline ---
OFFLINE_THRESHOLD_MINUTES=5

# --- Thresholds (métrica normalizada: metrica:operador:valor, separado por ;) ---
# Métricas comuns: ldr_value, temperature, humidity, battery_level (alias de volt_bateria)
THRESHOLD_RULES=ldr_value:>:500;battery_level:<:3.2
ALERT_COOLDOWN_MINUTES=5

# --- Alerta Telegram (deixe vazio para desativar) ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# --- Alerta E-mail / SMTP (deixe vazio para desativar) ---
SMTP_HOST=
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=
SMTP_PASS=
ALERT_EMAIL_FROM=
ALERT_EMAIL_TO=

# --- CORS (apenas para desenvolvimento com Vite; deixe vazio em produção) ---
CORS_ORIGIN=
```

- [ ] **Step 2: Create the docker-compose.yml**

`chirpstack-dashboard/docker-compose.yml`:

```yaml
services:
  postgres:
    image: timescale/timescaledb:latest-pg14
    restart: unless-stopped
    environment:
      POSTGRES_USER: dashboard
      POSTGRES_PASSWORD: dashboard
      POSTGRES_DB: dashboard
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dashboard -d dashboard"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ./backend
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgres://dashboard:dashboard@postgres:5432/dashboard
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "4000:4000"
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build: ./frontend
    restart: unless-stopped
    ports:
      - "5173:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 3: Create the .gitignore**

`chirpstack-dashboard/.gitignore`:

```
.env
**/node_modules/
**/dist/
```

- [ ] **Step 4: Validate compose config**

Run (from `chirpstack-dashboard`):

```bash
docker compose config
```

Expected: prints the resolved compose config without errors.

- [ ] **Step 5: Commit**

```bash
git add chirpstack-dashboard/docker-compose.yml chirpstack-dashboard/.env.example chirpstack-dashboard/.gitignore
git commit -m "feat(deploy): docker-compose, .env.example e .gitignore"
```

---

## Task 17: README.md

**Files:**
- Create: `chirpstack-dashboard/README.md`

- [ ] **Step 1: Create the README**

`chirpstack-dashboard/README.md`:

```markdown
# ChirpStack Dashboard

Dashboard em tempo real para monitorar telemetria LoRaWAN recebida via ChirpStack
(MQTT). Backend Node.js/TypeScript, banco PostgreSQL + TimescaleDB, frontend
React + Vite + TailwindCSS + Recharts e alertas via Telegram e/ou E-mail.

## Estrutura

- `backend/` — consumidor MQTT, API REST, Socket.io, persistência e motor de alertas
- `frontend/` — SPA React (cards, gráfico real-time, histórico e alertas)
- `docker-compose.yml` — orquestra backend, postgres (TimescaleDB) e frontend (nginx)

## Requisitos

- Docker + Docker Compose
- Stack ChirpStack em execução (ex.: `chirpstack-docker/`) com broker MQTT acessível

## Execução

```bash
cp .env.example .env
# edite .env conforme necessário (thresholds, telegram, e-mail)
docker compose up -d --build
```

Acesse http://localhost:5173

## Conectando ao broker MQTT do ChirpStack

Por padrão o backend usa `MQTT_URL=mqtt://host.docker.internal:1883` (com
`extra_hosts: host-gateway`), que alcança o Mosquitto exposto na porta 1883 do
host. Alternativa: coloque o dashboard na mesma rede Docker do ChirpStack e use
`MQTT_URL=mqtt://mosquitto:1883`.

## Thresholds (alertas)

Formato em `.env`: `THRESHOLD_RULES=metrica:operador:valor;...`

Operadores: `>`, `<`, `>=`, `<=`. Métricas normalizadas pelo parser:

- `ldr_value` — luminosidade (LDR)
- `temperature`, `humidity` — disponíveis quando o payload enviar
- `battery_level` — alias de `volt_bateria`

Cooldown: `ALERT_COOLDOWN_MINUTES` (padrão 5) entre alertas para o mesmo
device+métrica. Exemplo:

```bash
THRESHOLD_RULES=ldr_value:>:500;battery_level:<:3.2
ALERT_COOLDOWN_MINUTES=5
```

## API

- `GET /api/health` — status do serviço e do banco
- `GET /api/telemetry?device_eui=&from=&to=&limit=&offset=` — histórico paginado
- `GET /api/devices` — dispositivos com status Online/Offline
- `GET /api/alerts?limit=&offset=` — alertas registrados

WebSocket: o backend emite o evento `telemetry:new` com cada leitura em tempo real.

## Desenvolvimento local

Backend:

```bash
cd backend
npm install
npm run dev        # tsx watch, porta 4000
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # Vite, porta 5173 (proxy /api e /socket.io → 4000)
```

Testes (backend):

```bash
cd backend
npm test
```
```

- [ ] **Step 2: Commit**

```bash
git add chirpstack-dashboard/README.md
git commit -m "docs: README do chirpstack-dashboard"
```

---

## Task 18: Full verification (tests + builds + compose)

**Files:** none (verification only)

- [ ] **Step 1: Run backend tests**

Run (from `chirpstack-dashboard/backend`):

```bash
npm test
```

Expected: all Vitest suites pass (env 2, parser 5, rules 4, engine 3, persist 3).

- [ ] **Step 2: Typecheck + build backend**

Run:

```bash
npm run typecheck && npm run build
```

Expected: both exit 0; `dist/index.js` and `dist/db/init.sql` exist.

- [ ] **Step 3: Typecheck + build frontend**

Run (from `chirpstack-dashboard/frontend`):

```bash
npm run typecheck && npm run build
```

Expected: both exit 0; `dist/` produced.

- [ ] **Step 4: Validate compose + env file**

Run (from `chirpstack-dashboard`):

```bash
cp .env.example .env && docker compose config
```

Expected: compose config resolves without errors.

- [ ] **Step 5: End-to-end smoke test (optional, needs MQTT broker + running stack)**

```bash
docker compose up -d --build
curl -s http://localhost:4000/api/health
```

Expected: `{"status":"ok","db":"up",...}`. Publish a fake uplink to verify the pipeline:

```bash
docker run --rm --network host eclipse-mosquitto:2 mosquitto_pub -h localhost -p 1883 \
  -t 'application/1/device/0011223344556677/event/up' \
  -m '{"deviceInfo":{"deviceEui":"0011223344556677","deviceName":"esp-ldr-01","applicationId":"app-1"},"fCnt":1,"rxInfo":[{"rssi":-72,"snr":8.5}],"time":"2026-07-30T12:00:00Z","object":{"ldr_value":420,"volt_bateria":3.9}}'
curl -s 'http://localhost:4000/api/devices'
```

Expected: device `esp-ldr-01` appears in `api/devices` and in the frontend at http://localhost:5173.

- [ ] **Step 6: Final commit (if any changes) and confirm tree**

```bash
git add -A
git status
```

Expected: working tree clean (or only intended new files staged).

- [ ] **Step 7: Final verification of project tree**

Run:

```bash
find chirpstack-dashboard -type f -not -path '*/node_modules/*' -not -path '*/dist/*' | sort
```

Expected: the full file tree from the "File Structure" section above is present.

---

## Self-Review Summary

**Spec coverage:** MQTT consumer + parser (Task 3, 7), TimescaleDB schema + migration (Task 4), non-blocking batch persistence (Task 6), Socket.io real-time (Task 7), generic threshold engine with cooldown (Task 8), Telegram + Email notifiers (Task 9), REST endpoints (Task 10), frontend cards/chart/table/alerts + dark theme (Task 13, 14), docker-compose + .env.example + README (Task 16, 17), reconexão automática (mqtt.js `reconnectPeriod`, `waitForDb`).

**Placeholder scan:** no TBD/TODO; every code step contains full code.

**Type consistency:** `Reading`/`AlertEvent`/`AlertSender` defined once in `src/types.ts` and reused by parser, engine, notifiers, liveService; frontend `Reading` mirrors backend shape; `battery_level` alias consistent across parser, init.sql, rules, and frontend.
