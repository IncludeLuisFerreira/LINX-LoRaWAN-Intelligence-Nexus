# Sprint 1 — Reestruturação Multi-Tenant (Etapa 1 do PRD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evoluir o MVP mono-tenant `platform/` para a base **SaaS multi-tenant** do PRD Fase A — Etapa 1 (Estruturação Multi-Tenant & Autenticação): Prisma ORM, schema com `tenant_id`, autenticação JWT, middleware de isolamento e onboarding com dashboard padrão (RF05).

**Architecture:** Adota-se **Prisma ORM** como autoridade de schema/migrations e camada de dados do domínio de autenticação/onboarding (Tenants, Users, Dashboards). O domínio de ingestão em tempo real (`telemetry`, `devices`, `alerts`) mantém o `pg` Pool com SQL em lote já testado (caminho de alta vazão + hypertable TimescaleDB que o Prisma não gerencia nativamente); essas tabelas ganham `tenant_id` e seus repositórios se tornam tenant-aware. Autenticação JWT (Bcrypt) + middleware `requireAuth` protegem as rotas e escopam toda query por `tenant_id`.

**Tech Stack:** Node.js 20 + TypeScript + Express + Prisma ORM (PostgreSQL/TimescaleDB) + bcryptjs + jsonwebtoken + pg + MQTT.js + Socket.io + zod (backend, Vitest + supertest). Repo: `IncludeLuisFerreira/Servidor-LoRaWAN`, branch `plataforma-iot-integrada`. Todas as mudanças em `platform/backend/`.

**Issues do milestone "Sprint 1 - Reestruturação Multi-Tenant":** #1.. #14.

---

## Decisões de arquitetura (ler antes de executar)

1. **Prisma gerencia migrations de TODAS as tabelas, exceto `telemetry`** (hypertable). `telemetry` é criada de forma idempotente pelo `init.sql` no boot (extension timescaledb + `CREATE TABLE IF NOT EXISTS` + `create_hypertable`). `migrate.ts` permanece responsável pelo `init.sql`.
2. **Repositories de `telemetry`, `devices` e `alerts` continuam no `pg` Pool** (batch SQL otimizado, já coberto por testes de serviço). Apenas ganham parâmetros/colunas `tenant_id`. Os models Prisma de `Device`/`Alert` são usados para DDL (migration), mapeando as colunas existentes para que a migration apenas **adicione `tenant_id`**.
3. **Domínio de auth/onboarding usa Prisma Client** (`authService`, `dashboardTemplates`) com transação: Tenant + User + Dashboard padrão.
4. **ChirpStack REST (porta 8090) NÃO é chamado nesta sprint** — só a env `CHIRPSTACK_API_KEY`/`CHIRPSTACK_API_URL` é declarada (RF02 é Etapa 2). Sinalizar warn se ausente.
5. **Ingestão MQTT**: cada `Reading` ganha `tenantId` opcional. `persistService.flush()` resolve o tenant por `dev_eui` via `deviceRepository.resolveTenantsByDevEuis` e **descarta (com warn) leituras de dispositivos sem tenant** (isolamento estrito).
6. Migrations Prisma usam `--create-only` + edição manual do SQL para serem **idempotentes** em bancos já existentes (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`).

---

## File Structure (backend)

```
platform/backend/
├── prisma/
│   ├── schema.prisma                # models: Tenant, User, Device, Dashboard, Alert
│   └── migrations/                  # geradas por prisma migrate
├── src/
│   ├── index.ts                     # cria app via createApp() e escuta
│   ├── app.ts                       # NOVO: createApp() (testável via supertest)
│   ├── types.ts                     # + AuthContext, Reading.tenantId
│   ├── config/env.ts                # + JWT_SECRET, JWT_EXPIRES_IN, CHIRPSTACK_*
│   ├── db/
│   │   ├── pool.ts                  # inalterado
│   │   ├── migrate.ts               # inalterado (roda init.sql)
│   │   ├── init.sql                 # + tenant_id em telemetry e alerts; remove devices (Prisma)
│   │   └── prisma.ts                # NOVO: PrismaClient singleton
│   ├── middleware/
│   │   └── auth.ts                  # NOVO: requireAuth (Bearer JWT)
│   ├── services/
│   │   ├── authService.ts           # NOVO: register/login (bcryptjs + jwt + Prisma)
│   │   ├── dashboardTemplates.ts    # NOVO: template padrão §5.1 PRD
│   │   ├── persistService.ts        # + resolveTenantsByDevEuis no flush
│   │   └── thresholdEngine.ts       # + tenantId para alertRepository
│   ├── repositories/
│   │   ├── telemetryRepository.ts   # + tenant_id no insert e no query
│   │   ├── deviceRepository.ts      # + tenant_id + resolveTenantsByDevEuis
│   │   └── alertRepository.ts       # + tenant_id
│   └── routes/
│       ├── auth.ts                  # NOVO: POST /register, POST /login
│       ├── health.ts                # público (inalterado)
│       ├── telemetry.ts             # requireAuth + tenantId
│       ├── devices.ts               # requireAuth + tenantId
│       └── alerts.ts                # requireAuth + tenantId
└── test/
    ├── authService.test.ts          # NOVO
    ├── middlewareAuth.test.ts       # NOVO
    ├── isolation.test.ts            # NOVO (supertest + repos mockados)
    ├── dashboardTemplates.test.ts   # NOVO
    └── (atualizados) env, persistService, thresholdEngine
```

---

## Task 1 (Issue #1): Inicializar Prisma ORM no backend

**Files:**
- Create: `platform/backend/prisma/schema.prisma`
- Create: `platform/backend/src/db/prisma.ts`
- Modify: `platform/backend/package.json`
- Modify: `platform/backend/tsconfig.json`
- Modify: `platform/backend/Dockerfile`

- [ ] **Step 1: Instalar dependências**

Run (from `platform/backend`):

```bash
npm install @prisma/client@^5 && npm install -D prisma@^5
```

Expected: instala `@prisma/client` e `prisma`, gerando entradas em `package.json`.

- [ ] **Step 2: Adicionar scripts npm**

Em `platform/backend/package.json`, em `scripts`:

```json
"prisma:generate": "prisma generate",
"prisma:migrate": "prisma migrate dev",
"prisma:deploy": "prisma migrate deploy"
```

- [ ] **Step 3: Criar o schema.prisma inicial**

`platform/backend/prisma/schema.prisma`:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

Observação: `DATABASE_URL` já está no `.env` (usada pelo `pg`). O Prisma lê o mesmo `.env` via dotenv. Nenhum model ainda — serão adicionados nas Tasks 2 e 3.

- [ ] **Step 4: Criar o cliente singleton**

`platform/backend/src/db/prisma.ts`:

```ts
import { PrismaClient } from '@prisma/client'

export const prisma = new PrismaClient({
  log: ['warn', 'error'],
})
```

- [ ] **Step 5: Verificar generate e validate**

Run (from `platform/backend`):

```bash
npx prisma validate && npx prisma generate
```

Expected: `validate` OK; `generate` cria o client em `node_modules/.prisma/client`. `npm run typecheck` (tsc --noEmit) continua passando (o import de `src/db/prisma.ts` só passa após o generate — rodar generate antes).

- [ ] **Step 6: Atualizar o Dockerfile**

Em `platform/backend/Dockerfile`, no estágio `build`, após `RUN npm ci`:

```dockerfile
RUN npx prisma generate
```

E no estágio runtime, o `CMD` deve rodar migrations antes de subir:

```dockerfile
CMD ["sh", "-c", "npx prisma migrate deploy && node dist/index.js"]
```

Nota: `prisma` é devDependency e não estará no runtime (`--omit=dev`). Para o runtime usar `prisma migrate deploy`, mover `prisma` para `dependencies` no `package.json` (não devDependencies), ou copiar o CLI. **Decisão:** mover `prisma` (não `@prisma/client`) para `dependencies`. Edite `package.json` em `dependencies`: adicione `"prisma": "^5.0.0"` e remova de `devDependencies`. Rode `npm install` para sincronizar o lockfile.

- [ ] **Step 7: Commit**

```bash
git add platform/backend/prisma platform/backend/src/db/prisma.ts platform/backend/package.json platform/backend/package-lock.json platform/backend/tsconfig.json platform/backend/Dockerfile
git commit -m "feat(backend): inicializar Prisma ORM (schema, client, scripts, docker)"
```

---

## Task 2 (Issue #2): Schema Prisma — tenants e users

**Files:**
- Modify: `platform/backend/prisma/schema.prisma`

- [ ] **Step 1: Adicionar enum e models Tenant/User**

Substitua o conteúdo de `platform/backend/prisma/schema.prisma` por:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum Role {
  SUPER_ADMIN
  TENANT_ADMIN
  VIEWER
}

model Tenant {
  id         String      @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  name       String      @db.VarChar(100)
  createdAt  DateTime    @default(now()) @map("created_at") @db.Timestamptz
  users      User[]
  devices    Device[]
  dashboards Dashboard[]
}

model User {
  id           String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  tenantId     String   @map("tenant_id") @db.Uuid
  tenant       Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  email        String   @unique @db.VarChar(150)
  passwordHash String   @map("password_hash") @db.VarChar(255)
  role         Role     @default(TENANT_ADMIN)
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz
}
```

Observação: `dbgenerated("gen_random_uuid()")` requer PG 13+ (ok no `timescale/timescaledb:latest-pg14`).

- [ ] **Step 2: Gerar a migration**

Run (from `platform/backend`):

```bash
npx prisma migrate dev --name add-tenants-and-users
```

Expected: cria `prisma/migrations/<timestamp>_add-tenants-and-users/migration.sql` com `CREATE TYPE "Role"`, `CREATE TABLE "tenants"`, `CREATE TABLE "users"` e aplica no banco.

- [ ] **Step 3: Verificar**

Run:

```bash
npx prisma validate && npx prisma generate && npm run typecheck
```

Expected: tudo OK; `psql`/`docker exec` opcional: `\dt` mostra `tenants`, `users`.

- [ ] **Step 4: Commit**

```bash
git add platform/backend/prisma
git commit -m "feat(backend): schema Prisma — tenants e users (multi-tenant)"
```

---

## Task 3 (Issue #3): Schema Prisma — devices e dashboards

**Files:**
- Modify: `platform/backend/prisma/schema.prisma`

- [ ] **Step 1: Adicionar models Device e Dashboard**

Adicione ao final de `platform/backend/prisma/schema.prisma`:

```prisma
model Device {
  devEui         String    @id @map("dev_eui") @db.VarChar(16)
  tenantId       String    @map("tenant_id") @db.Uuid
  tenant         Tenant    @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  deviceName     String    @map("device_name") @db.Text
  applicationId  String    @map("application_id") @db.Text
  lastSeenAt     DateTime  @default(now()) @map("last_seen_at") @db.Timestamptz
  lastRssi       Int?      @map("last_rssi")
  lastSnr        Float?    @map("last_snr")
  createdAt      DateTime  @default(now()) @map("created_at") @db.Timestamptz
}

model Dashboard {
  id           String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  tenantId     String   @map("tenant_id") @db.Uuid
  tenant       Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)
  title        String   @default("Visão Geral") @db.VarChar(100)
  layoutConfig Json     @map("layout_config") @db.JsonB
  isDefault    Boolean  @default(true) @map("is_default")
  updatedAt    DateTime @default(now()) @updatedAt @map("updated_at") @db.Timestamptz
}
```

Observação: o model `Device` mapeia as **colunas existentes** da tabela `devices` (criada pelo `init.sql` antigo) para que a migration apenas adicione `tenant_id` e a FK, sem recriar/destruir dados.

- [ ] **Step 2: Gerar migration com --create-only (idempotente)**

Run (from `platform/backend`):

```bash
npx prisma migrate dev --name add-devices-and-dashboards --create-only
```

Abra `prisma/migrations/<timestamp>_add-devices-and-dashboards/migration.sql` e ajuste para idempotência:

```sql
CREATE TABLE IF NOT EXISTS "dashboards" (
    "id" UUID NOT NULL,
    "tenant_id" UUID NOT NULL,
    "title" VARCHAR(100) NOT NULL DEFAULT 'Visão Geral',
    "layout_config" JSONB NOT NULL,
    "is_default" BOOLEAN NOT NULL DEFAULT true,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "dashboards_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "devices" ADD COLUMN IF NOT EXISTS "tenant_id" UUID;

ALTER TABLE "devices" DROP CONSTRAINT IF EXISTS "devices_tenant_id_fkey";
ALTER TABLE "devices" ADD CONSTRAINT "devices_tenant_id_fkey"
    FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE INDEX IF NOT EXISTS "devices_tenant_id_idx" ON "devices"("tenant_id");
CREATE INDEX IF NOT EXISTS "dashboards_tenant_id_idx" ON "dashboards"("tenant_id");
CREATE INDEX IF NOT EXISTS "dashboards_tenant_id_is_default_idx" ON "dashboards"("tenant_id", "is_default");

ALTER TABLE "dashboards" DROP CONSTRAINT IF EXISTS "dashboards_tenant_id_fkey";
ALTER TABLE "dashboards" ADD CONSTRAINT "dashboards_tenant_id_fkey"
    FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
```

Importante: `tenant_id` em `devices` é **nullable** nesta migration (linhas legadas não têm tenant). A imposição de NOT NULL será tratada na Task 11 após backfill/limpeza. Ajuste os nomes das constraints geradas se o Prisma as nomear diferente.

- [ ] **Step 3: Aplicar e verificar**

Run:

```bash
npx prisma migrate dev
npx prisma validate && npx prisma generate && npm run typecheck
```

Expected: migration aplicada; `\d devices` mostra `tenant_id`; `\d dashboards` existe.

- [ ] **Step 4: Commit**

```bash
git add platform/backend/prisma
git commit -m "feat(backend): schema Prisma — devices e dashboards (tenant_id)"
```

---

## Task 4 (Issue #9): Env vars JWT_SECRET e CHIRPSTACK_API_KEY

**Files:**
- Modify: `platform/backend/src/config/env.ts`
- Modify: `platform/backend/.env.example`
- Modify: `platform/backend/.env`
- Modify: `platform/docker-compose.yml`
- Modify: `platform/backend/test/env.test.ts`

- [ ] **Step 1: Escrever o teste que falha**

Adicione em `platform/backend/test/env.test.ts` (mantendo os testes existentes):

```ts
it('adiciona defaults de JWT e ChirpStack', async () => {
  for (const key of ['JWT_SECRET', 'JWT_EXPIRES_IN', 'CHIRPSTACK_API_KEY', 'CHIRPSTACK_API_URL']) {
    delete process.env[key]
  }
  const { env } = await import('../src/config/env')
  expect(env.JWT_EXPIRES_IN).toBe('7d')
  expect(env.CHIRPSTACK_API_URL).toBe('http://chirpstack-rest-api:8090')
  expect(typeof env.JWT_SECRET).toBe('string')
  expect(env.JWT_SECRET.length).toBeGreaterThan(0)
})
```

- [ ] **Step 2: Rodar para ver falhar**

Run (from `platform/backend`):

```bash
npx vitest run test/env.test.ts
```

Expected: FAIL — `env.JWT_EXPIRES_IN` é `undefined`.

- [ ] **Step 3: Implementar no env.ts**

Em `platform/backend/src/config/env.ts`, adicione ao `EnvSchema`:

```ts
  JWT_SECRET: z
    .string()
    .default('dev-secret-change-me'),
  JWT_EXPIRES_IN: z.string().default('7d'),
  CHIRPSTACK_API_KEY: z.string().default(''),
  CHIRPSTACK_API_URL: z.string().default('http://chirpstack-rest-api:8090'),
```

- [ ] **Step 4: Rodar para ver passar**

Run:

```bash
npx vitest run test/env.test.ts
```

Expected: PASS (testes existentes + novo).

- [ ] **Step 5: Atualizar .env.example e .env**

Adicione ao final de `platform/.env.example`:

```
# --- Autenticação JWT ---
JWT_SECRET=dev-secret-change-me
JWT_EXPIRES_IN=7d

# --- ChirpStack REST API (provisionamento silencioso — Etapa 2) ---
CHIRPSTACK_API_KEY=
CHIRPSTACK_API_URL=http://chirpstack-rest-api:8090
```

Copie as mesmas linhas para `platform/.env` (valores de dev; `JWT_SECRET` deve ser trocado em produção).

- [ ] **Step 6: Atualizar docker-compose.yml**

Em `platform/docker-compose.yml`, no serviço `backend`, o bloco `env_file: .env` já injeta as variáveis automaticamente. Adicione também `JWT_SECRET` explícito ao `environment` para clareza:

```yaml
    environment:
      DATABASE_URL: postgres://dashboard:dashboard@postgres:5432/dashboard
      JWT_SECRET: ${JWT_SECRET:-dev-secret-change-me}
```

- [ ] **Step 7: Commit**

```bash
git add platform/backend/src/config/env.ts platform/.env.example platform/.env platform/docker-compose.yml platform/backend/test/env.test.ts
git commit -m "feat(backend): env vars JWT_SECRET e CHIRPSTACK_API_KEY"
```

---

## Task 5 (Issue #4): Migrations Prisma + hypertable de telemetria

**Files:**
- Modify: `platform/backend/src/db/init.sql`
- Modify: `platform/backend/src/db/migrate.ts` (se necessário)

- [ ] **Step 1: Atualizar init.sql**

Substitua `platform/backend/src/db/init.sql` por:

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS telemetry (
  id BIGSERIAL,
  device_eui TEXT NOT NULL,
  tenant_id UUID,
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
CREATE INDEX IF NOT EXISTS idx_telemetry_tenant_time ON telemetry (tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry (timestamp DESC);

CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID,
  device_eui TEXT NOT NULL,
  metric TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  threshold DOUBLE PRECISION NOT NULL,
  channel TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cooldown_until TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts (sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON alerts (tenant_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_tenant_device_metric ON alerts (tenant_id, device_eui, metric);
```

Removida a criação de `devices` (agora gerenciada pelo Prisma na Task 3). `alerts` permanece no `init.sql` porque é domínio de ingestão gerenciado pelo pg (não há model Prisma para ela). `telemetry` e `alerts` ganham `tenant_id UUID` (nullable — os repositórios sempre preenchem; NOT NULL adiado para evitar perda de dados legados).

Observação: se o `init.sql` antigo já criou `devices`, o Prisma a adiciona/alterou (Task 3). O `init.sql` idempotente agora só toca `telemetry` e `alerts`.

- [ ] **Step 2: Verificar boot idempotente**

Garanta que `src/db/migrate.ts` continue apenas lendo e executando `init.sql` (não muda). `init.sql` idempotente: rodar 2x não gera erro.

- [ ] **Step 3: Rodar build (copia init.sql para dist)**

Run (from `platform/backend`):

```bash
npm run build && ls dist/db/init.sql
```

Expected: build OK, `dist/db/init.sql` existe.

- [ ] **Step 4: Commit**

```bash
git add platform/backend/src/db/init.sql platform/backend/src/db/migrate.ts
git commit -m "feat(backend): hypertable de telemetria com tenant_id (init.sql idempotente)"
```

---

## Task 6 (Issue #13): Template padrão de dashboard no onboarding (RF05)

**Files:**
- Create: `platform/backend/src/services/dashboardTemplates.ts`
- Test: `platform/backend/test/dashboardTemplates.test.ts`

- [ ] **Step 1: Escrever o teste que falha**

`platform/backend/test/dashboardTemplates.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { DEFAULT_DASHBOARD_LAYOUT, buildDefaultDashboardInput } from '../src/services/dashboardTemplates'

describe('dashboardTemplates', () => {
  it('template padrão tem gridColumns 12 e 3 widgets (LDR + bateria + gráfico)', () => {
    expect(DEFAULT_DASHBOARD_LAYOUT.gridColumns).toBe(12)
    expect(DEFAULT_DASHBOARD_LAYOUT.widgets).toHaveLength(3)
    const types = DEFAULT_DASHBOARD_LAYOUT.widgets.map((w) => w.type)
    expect(types).toContain('STAT_CARD')
    expect(types).toContain('LINE_CHART')
  })

  it('buildDefaultDashboardInput cria payload do Prisma com isDefault true', () => {
    const input = buildDefaultDashboardInput('tenant-123')
    expect(input).toEqual({
      tenantId: 'tenant-123',
      title: 'Visão Geral',
      layoutConfig: DEFAULT_DASHBOARD_LAYOUT,
      isDefault: true,
    })
  })
})
```

- [ ] **Step 2: Rodar para ver falhar**

Run (from `platform/backend`):

```bash
npx vitest run test/dashboardTemplates.test.ts
```

Expected: FAIL — módulo `../src/services/dashboardTemplates` não encontrado.

- [ ] **Step 3: Implementar**

`platform/backend/src/services/dashboardTemplates.ts`:

```ts
import type { Prisma } from '@prisma/client'

export interface DashboardWidgetLayout {
  x: number
  y: number
  w: number
  h: number
}

export interface DashboardWidget {
  id: string
  type: 'STAT_CARD' | 'LINE_CHART'
  title: string
  metricPath: string
  unit?: string
  timeRange?: string
  layout: DashboardWidgetLayout
}

export interface DashboardLayout {
  gridColumns: number
  widgets: DashboardWidget[]
}

export const DEFAULT_DASHBOARD_LAYOUT: DashboardLayout = {
  gridColumns: 12,
  widgets: [
    {
      id: 'card_ldr_1',
      type: 'STAT_CARD',
      title: 'Nível de Luminosidade',
      metricPath: 'ldr',
      unit: 'ADC',
      layout: { x: 0, y: 0, w: 6, h: 2 },
    },
    {
      id: 'card_bat_1',
      type: 'STAT_CARD',
      title: 'Bateria do Nó',
      metricPath: 'v_bat',
      unit: 'mV',
      layout: { x: 6, y: 0, w: 6, h: 2 },
    },
    {
      id: 'chart_telemetry_1',
      type: 'LINE_CHART',
      title: 'Histórico de Luminosidade',
      metricPath: 'ldr',
      timeRange: '24h',
      layout: { x: 0, y: 2, w: 12, h: 4 },
    },
  ],
}

export function buildDefaultDashboardInput(tenantId: string): Prisma.DashboardUncheckedCreateInput {
  return {
    tenantId,
    title: 'Visão Geral',
    layoutConfig: DEFAULT_DASHBOARD_LAYOUT,
    isDefault: true,
  }
}
```

Observação: usamos `DashboardUncheckedCreateInput` (aceita a FK scalar `tenantId`). No runtime, `tx.dashboard.create({ data })` aceita tanto `CreateInput` quanto `UncheckedCreateInput` (union no tipo `XCreateArgs`), então o objeto com `tenantId` typechecka sem `connect`.

- [ ] **Step 4: Rodar para ver passar**

Run:

```bash
npx vitest run test/dashboardTemplates.test.ts && npm run typecheck
```

Expected: PASS (2 testes) e typecheck OK.

- [ ] **Step 5: Commit**

```bash
git add platform/backend/src/services/dashboardTemplates.ts platform/backend/test/dashboardTemplates.test.ts
git commit -m "feat(backend): template padrão de dashboard (LDR + bateria) para onboarding RF05"
```

---

## Task 7 (Issue #5): Registro de tenant + usuário admin (register)

**Files:**
- Modify: `platform/backend/package.json`
- Create: `platform/backend/src/services/authService.ts`
- Create: `platform/backend/src/routes/auth.ts`
- Modify: `platform/backend/src/app.ts` (será criado na Task 10 — nesta task, registrar rota em `index.ts`; ver nota)
- Modify: `platform/backend/src/index.ts`
- Test: `platform/backend/test/authService.test.ts`

Nota de dependência: para testes de rota via supertest, a Task 10 cria `src/app.ts`. Nesta task, exponha a rota de auth montada em `index.ts` e teste o `authService` isoladamente. Se preferir adiantar `createApp()`, faça na Task 10 e ajuste aqui depois.

- [ ] **Step 1: Instalar dependências de auth**

Run (from `platform/backend`):

```bash
npm install bcryptjs jsonwebtoken && npm install -D @types/bcryptjs @types/jsonwebtoken
```

- [ ] **Step 2: Escrever o teste que falha**

`platform/backend/test/authService.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import bcrypt from 'bcryptjs'

vi.mock('../src/db/prisma', () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      create: vi.fn(),
    },
    tenant: {
      create: vi.fn(),
    },
    dashboard: {
      create: vi.fn(),
    },
    $transaction: vi.fn(),
  },
}))

import { prisma } from '../src/db/prisma'
import { AuthService, AuthError } from '../src/services/authService'

const prismaMock = prisma as unknown as {
  user: { findUnique: ReturnType<typeof vi.fn>; create: ReturnType<typeof vi.fn> }
  tenant: { create: ReturnType<typeof vi.fn> }
  dashboard: { create: ReturnType<typeof vi.fn> }
  $transaction: ReturnType<typeof vi.fn>
}

describe('AuthService.register', () => {
  let service: AuthService

  beforeEach(() => {
    service = new AuthService(prisma as any)
    vi.resetAllMocks()
    prismaMock.$transaction.mockImplementation(async (fn: (tx: any) => Promise<unknown>) => fn(prisma))
  })

  it('cria tenant, admin e dashboard padrão em transação', async () => {
    prismaMock.user.findUnique.mockResolvedValue(null)
    prismaMock.tenant.create.mockResolvedValue({ id: 'tenant-1', name: 'IFSULDEMINAS' })
    prismaMock.user.create.mockResolvedValue({
      id: 'user-1',
      tenantId: 'tenant-1',
      email: 'admin@ifsul.edu.br',
      role: 'TENANT_ADMIN',
      passwordHash: 'hashed',
    })
    prismaMock.dashboard.create.mockResolvedValue({ id: 'dash-1' })

    const result = await service.register({
      tenantName: 'IFSULDEMINAS',
      email: 'admin@ifsul.edu.br',
      password: 'senha-forte-123',
    })

    expect(prismaMock.tenant.create).toHaveBeenCalledWith({ data: { name: 'IFSULDEMINAS' } })
    expect(prismaMock.user.create).toHaveBeenCalled()
    expect(prismaMock.dashboard.create).toHaveBeenCalled()
    expect(result.user).toMatchObject({ email: 'admin@ifsul.edu.br', role: 'TENANT_ADMIN', tenant_id: 'tenant-1' })
    expect(result.user).not.toHaveProperty('passwordHash')
    expect(typeof result.token).toBe('string')
  })

  it('lança EMAIL_TAKEN se e-mail já existe', async () => {
    prismaMock.user.findUnique.mockResolvedValue({ id: 'user-9' })
    await expect(
      service.register({ tenantName: 'X', email: 'dup@x.com', password: 'senha-forte-123' })
    ).rejects.toMatchObject({ code: 'EMAIL_TAKEN' })
  })

  it('rejeita senha fraca', async () => {
    prismaMock.user.findUnique.mockResolvedValue(null)
    await expect(
      service.register({ tenantName: 'X', email: 'a@b.com', password: '123' })
    ).rejects.toMatchObject({ code: 'WEAK_PASSWORD' })
  })

  it('armazena hash bcrypt e nunca a senha em texto puro', async () => {
    prismaMock.user.findUnique.mockResolvedValue(null)
    prismaMock.tenant.create.mockResolvedValue({ id: 'tenant-1' })
    prismaMock.user.create.mockImplementation(async ({ data }: any) => ({
      id: 'user-1',
      tenantId: 'tenant-1',
      email: data.email,
      role: 'TENANT_ADMIN',
      passwordHash: data.passwordHash,
    }))
    prismaMock.dashboard.create.mockResolvedValue({ id: 'dash-1' })

    await service.register({ tenantName: 'T', email: 'h@h.com', password: 'senha-forte-123' })
    const created = prismaMock.user.create.mock.calls[0][0].data as { passwordHash: string }
    expect(created.passwordHash).not.toBe('senha-forte-123')
    expect(await bcrypt.compare('senha-forte-123', created.passwordHash)).toBe(true)
  })
})

describe('AuthError', () => {
  it('carrega code e status', () => {
    const err = new AuthError('EMAIL_TAKEN', 409)
    expect(err.code).toBe('EMAIL_TAKEN')
    expect(err.status).toBe(409)
  })
})
```

- [ ] **Step 3: Rodar para ver falhar**

Run (from `platform/backend`):

```bash
npx vitest run test/authService.test.ts
```

Expected: FAIL — módulo `../src/services/authService` não encontrado.

- [ ] **Step 4: Implementar o AuthService**

`platform/backend/src/services/authService.ts`:

```ts
import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'
import type { PrismaClient, Role } from '@prisma/client'
import { env } from '../config/env'
import { buildDefaultDashboardInput } from './dashboardTemplates'

export class AuthError extends Error {
  constructor(
    readonly code: string,
    readonly status = 400,
    message?: string
  ) {
    super(message ?? code)
  }
}

export interface PublicUser {
  id: string
  email: string
  role: Role
  tenant_id: string
}

export interface AuthResult {
  token: string
  user: PublicUser
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MIN_PASSWORD = 8

export class AuthService {
  constructor(private readonly db: PrismaClient) {}

  async register(input: { tenantName: string; email: string; password: string }): Promise<AuthResult> {
    const email = input.email.trim().toLowerCase()
    const tenantName = input.tenantName.trim()
    if (!EMAIL_RE.test(email)) throw new AuthError('INVALID_EMAIL', 400)
    if (input.password.length < MIN_PASSWORD) throw new AuthError('WEAK_PASSWORD', 400)
    if (tenantName.length === 0) throw new AuthError('INVALID_TENANT_NAME', 400)

    const existing = await this.db.user.findUnique({ where: { email } })
    if (existing) throw new AuthError('EMAIL_TAKEN', 409)

    const passwordHash = await bcrypt.hash(input.password, 10)

    const created = await this.db.$transaction(async (tx) => {
      const tenant = await tx.tenant.create({ data: { name: tenantName } })
      const user = await tx.user.create({
        data: {
          tenantId: tenant.id,
          email,
          passwordHash,
          role: 'TENANT_ADMIN',
        },
      })
      await tx.dashboard.create({
        data: buildDefaultDashboardInput(tenant.id),
      })
      return { tenantId: tenant.id, user }
    })

    return this.toResult(created.user, created.tenantId)
  }

  async login(input: { email: string; password: string }): Promise<AuthResult> {
    const email = input.email.trim().toLowerCase()
    const user = await this.db.user.findUnique({ where: { email } })
    if (!user) throw new AuthError('INVALID_CREDENTIALS', 401)
    const ok = await bcrypt.compare(input.password, user.passwordHash)
    if (!ok) throw new AuthError('INVALID_CREDENTIALS', 401)
    return this.toResult(user, user.tenantId)
  }

  private toResult(user: { id: string; email: string; role: Role; tenantId: string }, tenantId: string): AuthResult {
    const token = jwt.sign(
      { user_id: user.id, tenant_id: tenantId, role: user.role },
      env.JWT_SECRET,
      { expiresIn: env.JWT_EXPIRES_IN } as jwt.SignOptions
    )
    return {
      token,
      user: {
        id: user.id,
        email: user.email,
        role: user.role,
        tenant_id: tenantId,
      },
    }
  }
}
```

- [ ] **Step 5: Criar a rota de auth**

`platform/backend/src/routes/auth.ts`:

```ts
import { Router } from 'express'
import { AuthService, AuthError } from '../services/authService'
import { prisma } from '../db/prisma'

export const authRouter = Router()
const auth = new AuthService(prisma)

authRouter.post('/register', async (req, res, next) => {
  try {
    const { tenantName, email, password } = req.body ?? {}
    const result = await auth.register({ tenantName, email, password })
    res.status(201).json(result)
  } catch (err) {
    next(err)
  }
})

authRouter.post('/login', async (req, res, next) => {
  try {
    const { email, password } = req.body ?? {}
    const result = await auth.login({ email, password })
    res.json(result)
  } catch (err) {
    next(err)
  }
})

export function isAuthError(err: unknown): err is AuthError {
  return err instanceof AuthError
}
```

- [ ] **Step 6: Montar a rota em index.ts**

Em `platform/backend/src/index.ts`, adicione os imports:

```ts
import { authRouter, isAuthError } from './routes/auth'
```

Monte a rota:

```ts
app.use('/api/auth', authRouter)
```

E adicione um handler de erro genérico antes do `server.listen` (para mapear `AuthError` → status HTTP):

```ts
app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  if (isAuthError(err)) {
    res.status(err.status).json({ error: err.code })
    return
  }
  logger.error('[http] Erro não tratado', err)
  res.status(500).json({ error: 'INTERNAL_ERROR' })
})
```

Observação: `logger` já é importado em `index.ts`.

- [ ] **Step 7: Rodar testes e typecheck**

Run (from `platform/backend`):

```bash
npx vitest run test/authService.test.ts && npm run typecheck
```

Expected: PASS e typecheck OK.

- [ ] **Step 8: Commit**

```bash
git add platform/backend/src/services/authService.ts platform/backend/src/routes/auth.ts platform/backend/src/index.ts platform/backend/test/authService.test.ts platform/backend/package.json platform/backend/package-lock.json
git commit -m "feat(backend): registro de tenant + usuário admin com JWT (register)"
```

---

## Task 8 (Issue #6): Login JWT

**Files:**
- Modify: `platform/backend/src/services/authService.ts`
- Modify: `platform/backend/test/authService.test.ts`

Nota: `login` já foi implementado em `authService` na Task 7 (rota `POST /api/auth/login` montada). Esta task completa a cobertura de testes de login.

- [ ] **Step 1: Adicionar testes de login**

Adicione em `platform/backend/test/authService.test.ts`:

```ts
describe('AuthService.login', () => {
  let service: AuthService

  beforeEach(() => {
    service = new AuthService(prisma as any)
    vi.resetAllMocks()
  })

  it('retorna token e usuário com tenant_id e role no payload', async () => {
    const passwordHash = await bcrypt.hash('senha-forte-123', 10)
    prismaMock.user.findUnique.mockResolvedValue({
      id: 'user-1',
      tenantId: 'tenant-1',
      email: 'admin@ifsul.edu.br',
      role: 'TENANT_ADMIN',
      passwordHash,
    })
    const result = await service.login({ email: 'ADMIN@ifsul.edu.br', password: 'senha-forte-123' })
    expect(result.user.tenant_id).toBe('tenant-1')
    expect(result.user.role).toBe('TENANT_ADMIN')
    const payload = JSON.parse(Buffer.from(result.token.split('.')[1], 'base64url').toString())
    expect(payload).toMatchObject({ user_id: 'user-1', tenant_id: 'tenant-1', role: 'TENANT_ADMIN' })
  })

  it('rejeita senha incorreta com INVALID_CREDENTIALS', async () => {
    const passwordHash = await bcrypt.hash('senha-forte-123', 10)
    prismaMock.user.findUnique.mockResolvedValue({
      id: 'user-1',
      tenantId: 'tenant-1',
      email: 'a@b.com',
      role: 'TENANT_ADMIN',
      passwordHash,
    })
    await expect(
      service.login({ email: 'a@b.com', password: 'senha-errada' })
    ).rejects.toMatchObject({ code: 'INVALID_CREDENTIALS' })
  })

  it('rejeita e-mail inexistente com INVALID_CREDENTIALS (genérico)', async () => {
    prismaMock.user.findUnique.mockResolvedValue(null)
    await expect(
      service.login({ email: 'nope@x.com', password: 'qualquer' })
    ).rejects.toMatchObject({ code: 'INVALID_CREDENTIALS' })
  })
})
```

- [ ] **Step 2: Rodar para ver passar**

Run (from `platform/backend`):

```bash
npx vitest run test/authService.test.ts
```

Expected: PASS (todos os testes de register + login).

- [ ] **Step 3: Commit**

```bash
git add platform/backend/src/services/authService.ts platform/backend/test/authService.test.ts
git commit -m "feat(backend): login JWT com payload user_id/tenant_id/role"
```

---

## Task 9 (Issue #7): Middleware de autenticação (Bearer JWT)

**Files:**
- Modify: `platform/backend/src/types.ts`
- Create: `platform/backend/src/middleware/auth.ts`
- Test: `platform/backend/test/middlewareAuth.test.ts`

- [ ] **Step 1: Adicionar AuthContext aos tipos**

Em `platform/backend/src/types.ts`, adicione:

```ts
export interface AuthContext {
  userId: string
  tenantId: string
  role: string
}
```

- [ ] **Step 2: Escrever o teste que falha**

`platform/backend/test/middlewareAuth.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Request, Response, NextFunction } from 'express'
import jwt from 'jsonwebtoken'

vi.mock('../src/config/env', () => ({
  env: { JWT_SECRET: 'test-secret' },
}))

import { requireAuth } from '../src/middleware/auth'

const SECRET = 'test-secret'

function makeReq(headers: Record<string, string> = {}): Request {
  return { headers } as Request
}

function makeRes() {
  const res: any = {}
  res.status = vi.fn(() => res)
  res.json = vi.fn(() => res)
  return res as Response & { status: ReturnType<typeof vi.fn>; json: ReturnType<typeof vi.fn> }
}

describe('requireAuth', () => {
  let next: NextFunction

  beforeEach(() => {
    next = vi.fn()
  })

  it('preenche req.auth com token válido', () => {
    const token = jwt.sign({ user_id: 'u1', tenant_id: 't1', role: 'TENANT_ADMIN' }, SECRET)
    const req = makeReq({ authorization: `Bearer ${token}` })
    const res = makeRes()
    requireAuth(req, res, next)
    expect(req.auth).toMatchObject({ userId: 'u1', tenantId: 't1', role: 'TENANT_ADMIN' })
    expect(next).toHaveBeenCalled()
    expect(res.status).not.toHaveBeenCalled()
  })

  it('retorna 401 sem header Authorization', () => {
    const req = makeReq()
    const res = makeRes()
    requireAuth(req, res, next)
    expect(res.status).toHaveBeenCalledWith(401)
    expect(next).not.toHaveBeenCalled()
  })

  it('retorna 401 com token expirado', () => {
    const token = jwt.sign({ user_id: 'u1', tenant_id: 't1', role: 'VIEWER' }, SECRET, { expiresIn: '-1s' })
    const req = makeReq({ authorization: `Bearer ${token}` })
    const res = makeRes()
    requireAuth(req, res, next)
    expect(res.status).toHaveBeenCalledWith(401)
  })

  it('retorna 401 com assinatura inválida', () => {
    const token = jwt.sign({ user_id: 'u1', tenant_id: 't1', role: 'VIEWER' }, 'outra-chave')
    const req = makeReq({ authorization: `Bearer ${token}` })
    const res = makeRes()
    requireAuth(req, res, next)
    expect(res.status).toHaveBeenCalledWith(401)
  })
})
```

- [ ] **Step 3: Rodar para ver falhar**

Run (from `platform/backend`):

```bash
npx vitest run test/middlewareAuth.test.ts
```

Expected: FAIL — módulo `../src/middleware/auth` não encontrado.

- [ ] **Step 4: Implementar o middleware**

`platform/backend/src/middleware/auth.ts`:

```ts
import type { NextFunction, Request, Response } from 'express'
import jwt from 'jsonwebtoken'
import { env } from '../config/env'
import type { AuthContext } from '../types'

declare global {
  namespace Express {
    interface Request {
      auth?: AuthContext
    }
  }
}

interface JwtClaims {
  user_id: string
  tenant_id: string
  role: string
}

export function requireAuth(req: Request, res: Response, next: NextFunction): void {
  const header = req.headers.authorization
  if (!header || !header.startsWith('Bearer ')) {
    res.status(401).json({ error: 'UNAUTHORIZED' })
    return
  }
  const token = header.slice('Bearer '.length)
  try {
    const claims = jwt.verify(token, env.JWT_SECRET) as JwtClaims
    req.auth = {
      userId: claims.user_id,
      tenantId: claims.tenant_id,
      role: claims.role,
    }
    next()
  } catch {
    res.status(401).json({ error: 'UNAUTHORIZED' })
  }
}
```

- [ ] **Step 5: Rodar para ver passar**

Run:

```bash
npx vitest run test/middlewareAuth.test.ts && npm run typecheck
```

Expected: PASS (4 testes) e typecheck OK.

- [ ] **Step 6: Commit**

```bash
git add platform/backend/src/types.ts platform/backend/src/middleware/auth.ts platform/backend/test/middlewareAuth.test.ts
git commit -m "feat(backend): middleware de autenticação Bearer JWT"
```

---

## Task 10 (Issue #8): Proteger rotas e isolar por tenant_id

**Files:**
- Create: `platform/backend/src/app.ts`
- Modify: `platform/backend/src/index.ts`
- Modify: `platform/backend/src/routes/telemetry.ts`
- Modify: `platform/backend/src/routes/devices.ts`
- Modify: `platform/backend/src/routes/alerts.ts`
- Modify: `platform/backend/package.json` (supertest)
- Test: `platform/backend/test/isolation.test.ts`

- [ ] **Step 1: Instalar supertest**

Run (from `platform/backend`):

```bash
npm install -D supertest @types/supertest
```

- [ ] **Step 2: Extrair createApp()**

Crie `platform/backend/src/app.ts`:

```ts
import http from 'node:http'
import express from 'express'
import cors from 'cors'
import { Server } from 'socket.io'
import { env } from './config/env'
import { logger } from './utils/logger'
import { healthRouter } from './routes/health'
import { authRouter, isAuthError } from './routes/auth'
import { telemetryRouter } from './routes/telemetry'
import { devicesRouter } from './routes/devices'
import { alertsRouter } from './routes/alerts'
import { requireAuth } from './middleware/auth'

export function createApp() {
  const app = express()
  app.use(express.json())
  if (env.CORS_ORIGIN) app.use(cors({ origin: env.CORS_ORIGIN }))

  app.use('/api/health', healthRouter)
  app.use('/api/auth', authRouter)

  app.use('/api/telemetry', requireAuth, telemetryRouter)
  app.use('/api/devices', requireAuth, devicesRouter)
  app.use('/api/alerts', requireAuth, alertsRouter)

  app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    if (isAuthError(err)) {
      res.status(err.status).json({ error: err.code })
      return
    }
    logger.error('[http] Erro não tratado', err)
    res.status(500).json({ error: 'INTERNAL_ERROR' })
  })

  const server = http.createServer(app)
  const io = new Server(server, {
    cors: { origin: env.CORS_ORIGIN ?? true },
  })
  return { app, server, io }
}
```

- [ ] **Step 3: Refatorar index.ts**

Substitua o conteúdo de `platform/backend/src/index.ts` por:

```ts
import { createApp } from './app'
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

async function main(): Promise<void> {
  await waitForDb()
  await migrate()

  const { server, io } = createApp()
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

- [ ] **Step 4: Escrever o teste de isolamento (falha primeiro)**

`platform/backend/test/isolation.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import request from 'supertest'
import jwt from 'jsonwebtoken'

vi.mock('../src/config/env', () => ({
  env: {
    JWT_SECRET: 'test-secret',
    JWT_EXPIRES_IN: '7d',
    CORS_ORIGIN: undefined,
    OFFLINE_THRESHOLD_MINUTES: 5,
  },
}))

vi.mock('../src/db/prisma', () => ({
  prisma: {
    user: { findUnique: vi.fn().mockResolvedValue(null) },
    tenant: { create: vi.fn() },
    dashboard: { create: vi.fn() },
    $transaction: vi.fn(),
  },
}))

vi.mock('../src/db/pool', () => ({
  pool: { query: vi.fn().mockResolvedValue({ rows: [] }) },
}))

vi.mock('../src/repositories/telemetryRepository', () => ({
  queryTelemetry: vi.fn(),
}))
vi.mock('../src/repositories/deviceRepository', () => ({
  listDevices: vi.fn(),
}))
vi.mock('../src/repositories/alertRepository', () => ({
  listAlerts: vi.fn(),
}))

import { createApp } from '../src/app'
import { queryTelemetry } from '../src/repositories/telemetryRepository'
import { listDevices } from '../src/repositories/deviceRepository'
import { listAlerts } from '../src/repositories/alertRepository'

const queryTelemetryMock = queryTelemetry as ReturnType<typeof vi.fn>
const listDevicesMock = listDevices as ReturnType<typeof vi.fn>
const listAlertsMock = listAlerts as ReturnType<typeof vi.fn>

function token(tenantId: string, role = 'TENANT_ADMIN'): string {
  return jwt.sign({ user_id: 'u1', tenant_id: tenantId, role }, 'test-secret')
}

describe('Isolamento por tenant_id', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    queryTelemetryMock.mockResolvedValue({ rows: [], total: 0 })
    listDevicesMock.mockResolvedValue([])
    listAlertsMock.mockResolvedValue({ rows: [], total: 0 })
  })

  it('401 sem token nas rotas de dados', async () => {
    const { app } = createApp()
    for (const path of ['/api/telemetry', '/api/devices', '/api/alerts']) {
      const res = await request(app).get(path)
      expect(res.status).toBe(401)
    }
  })

  it('health e auth permanecem públicos', async () => {
    const { app } = createApp()
    expect((await request(app).get('/api/health')).status).toBe(200)
    expect((await request(app).post('/api/auth/login').send({})).status).not.toBe(401)
  })

  it('telemetry é consultado com o tenant_id do token', async () => {
    const { app } = createApp()
    const res = await request(app)
      .get('/api/telemetry')
      .set('Authorization', `Bearer ${token('tenant-a')}`)
    expect(res.status).toBe(200)
    expect(queryTelemetryMock).toHaveBeenCalledWith(
      expect.objectContaining({ tenantId: 'tenant-a' })
    )
  })

  it('devices é listado com o tenant_id do token', async () => {
    const { app } = createApp()
    await request(app)
      .get('/api/devices')
      .set('Authorization', `Bearer ${token('tenant-b')}`)
    expect(listDevicesMock).toHaveBeenCalledWith(expect.objectContaining({ tenantId: 'tenant-b' }))
  })

  it('alerts é listado com o tenant_id do token', async () => {
    const { app } = createApp()
    await request(app)
      .get('/api/alerts')
      .set('Authorization', `Bearer ${token('tenant-c')}`)
    expect(listAlertsMock).toHaveBeenCalledWith(expect.objectContaining({ tenantId: 'tenant-c' }))
  })
})
```

- [ ] **Step 5: Rodar para ver falhar**

Run (from `platform/backend`):

```bash
npx vitest run test/isolation.test.ts
```

Expected: FAIL — routes não usam `req.auth.tenantId` (asserts de chamada com `tenantId` falham; e typecheck falha pois repositories ainda não aceitam `tenantId`).

- [ ] **Step 6: Ajustar as rotas (contrato de tenantId)**

`platform/backend/src/routes/telemetry.ts`:

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
    const { rows, total } = await queryTelemetry({
      tenantId: req.auth!.tenantId,
      deviceEui,
      from,
      to,
      limit,
      offset,
    })
    res.json({ rows, total, limit, offset })
  } catch (err) {
    next(err)
  }
})
```

`platform/backend/src/routes/devices.ts`:

```ts
import { Router } from 'express'
import { listDevices } from '../repositories/deviceRepository'

export const devicesRouter = Router()

devicesRouter.get('/', async (req, res, next) => {
  try {
    const devices = await listDevices({ tenantId: req.auth!.tenantId })
    res.json({ devices })
  } catch (err) {
    next(err)
  }
})
```

`platform/backend/src/routes/alerts.ts`:

```ts
import { Router } from 'express'
import { listAlerts } from '../repositories/alertRepository'

export const alertsRouter = Router()

alertsRouter.get('/', async (req, res, next) => {
  try {
    const limit = Math.min(Math.max(Number(req.query.limit) || 20, 1), 200)
    const offset = Math.max(Number(req.query.offset) || 0, 0)
    const { rows, total } = await listAlerts({
      tenantId: req.auth!.tenantId,
      limit,
      offset,
    })
    res.json({ rows, total, limit, offset })
  } catch (err) {
    next(err)
  }
})
```

Nota: o typecheck falhará até as Tasks 11/12/13 implementarem as novas assinaturas dos repositories. Para isolar o progresso, execute o teste com `npx vitest run test/isolation.test.ts` mesmo com erro de tipo (Vitest transpila por arquivo). Corrija os repositories nas Tasks 11-13 e rode typecheck completo no final.

- [ ] **Step 7: Rodar o teste de isolamento**

Run:

```bash
npx vitest run test/isolation.test.ts
```

Expected: PASS (5 testes) após as Tasks 11-13 ajustarem as assinaturas dos repositories. Se necessário, interrompa aqui e continue nas Tasks 11-13 antes de afirmar o verde.

- [ ] **Step 8: Commit (após Tasks 11-13)**

```bash
git add platform/backend/src/app.ts platform/backend/src/index.ts platform/backend/src/routes platform/backend/test/isolation.test.ts platform/backend/package.json platform/backend/package-lock.json
git commit -m "feat(backend): proteger rotas e isolar consultas por tenant_id"
```

---

## Task 11 (Issue #10): telemetryRepository tenant-aware

**Files:**
- Modify: `platform/backend/src/repositories/telemetryRepository.ts`
- Modify: `platform/backend/src/services/persistService.ts`
- Modify: `platform/backend/src/types.ts`
- Modify: `platform/backend/test/persistService.test.ts`

- [ ] **Step 1: Adicionar tenantId ao tipo Reading**

Em `platform/backend/src/types.ts`, no `Reading`:

```ts
export interface Reading {
  deviceEui: string
  deviceName: string
  applicationId: string
  tenantId?: string
  fCnt?: number
  rssi?: number
  snr?: number
  metrics: MetricValue
  timestamp: string
  raw: unknown
}
```

- [ ] **Step 2: Atualizar o repositório**

`platform/backend/src/repositories/telemetryRepository.ts` (mudanças):

```ts
const NUMERIC_COLUMNS = 12

export async function insertTelemetryBatch(readings: Reading[]): Promise<void> {
  if (readings.length === 0) return
  const values: unknown[] = []
  const rows: unknown[][] = []
  for (const r of readings) {
    rows.push([
      r.deviceEui,
      r.tenantId ?? null,
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
       (device_eui, tenant_id, device_name, application_id, temperature, humidity, battery_level,
        rssi, snr, fcnt, payload, timestamp)
     VALUES ${placeholders}`,
    values
  )
}

export interface TelemetryQuery {
  tenantId: string
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
  params.push(q.tenantId)
  conditions.push(`tenant_id = $${params.length}`)
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
  // ... demais query igual, apenas com tenantId obrigatório
}
```

Mantenha `TelemetryRow` com `id`, `device_eui`, etc. (sem mudança de shape de resposta).

- [ ] **Step 3: Atualizar persistService com resolução de tenant**

`platform/backend/src/services/persistService.ts`:

```ts
import { insertTelemetryBatch } from '../repositories/telemetryRepository'
import { upsertDevices, resolveTenantsByDevEuis } from '../repositories/deviceRepository'
import { waitForDb } from '../db/pool'
import { env } from '../config/env'
import { logger } from '../utils/logger'
import type { Reading } from '../types'

export class PersistService {
  private readonly queueMaxSize: number
  private queue: Reading[] = []
  private timer: NodeJS.Timeout | null = null
  private flushing = false

  constructor(queueMaxSize = env.QUEUE_MAX_SIZE) {
    this.queueMaxSize = queueMaxSize
  }

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
    if (this.queue.length >= this.queueMaxSize) {
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
      await this.resolveTenants(batch)
      await insertTelemetryBatch(batch)
      await upsertDevices(batch)
    } catch (err) {
      logger.error('[persist] Erro ao gravar lote, reenfileirando', err)
      this.queue.unshift(...batch)
    } finally {
      this.flushing = false
    }
  }

  private async resolveTenants(batch: Reading[]): Promise<void> {
    const euis = [...new Set(batch.map((r) => r.deviceEui))]
    const map = await resolveTenantsByDevEuis(euis)
    for (const reading of batch) {
      reading.tenantId = map.get(reading.deviceEui)
      if (!reading.tenantId) {
        logger.warn(`[persist] Dispositivo sem tenant ignorado: ${reading.deviceEui}`)
      }
    }
  }
}
```

Observação: leituras sem tenant são ignoradas na gravação (isolamento), mas o array ainda as carrega (são descartadas pelo INSERT com `tenant_id NULL`). Para evitar gravação de telemetria órfã, filtre em `insertTelemetryBatch`: pule leituras sem `tenantId`. Ajuste `insertTelemetryBatch` para:

```ts
const valid = readings.filter((r) => r.tenantId)
if (valid.length === 0) return
// use `valid` no restante
```

- [ ] **Step 4: Atualizar testes de persistService**

Em `platform/backend/test/persistService.test.ts`:

- Adicione `resolveTenantsByDevEuis` ao mock de `deviceRepository`:

```ts
vi.mock('../src/repositories/deviceRepository', () => ({
  upsertDevices: mocks.upsertDevices,
  resolveTenantsByDevEuis: mocks.resolveTenantsByDevEuis,
}))
```

- Em `mocks` (hoisted), adicione `resolveTenantsByDevEuis: vi.fn()`.
- No `beforeEach`, configure: `mocks.resolveTenantsByDevEuis.mockImplementation(async (euis: string[]) => new Map(euis.map((e) => [e, 'tenant-1'])))`.
- Atualize `makeReading` para incluir `tenantId: 'tenant-1'`.
- Adicione um teste:

```ts
it('descarta leituras de dispositivos sem tenant', async () => {
  mocks.resolveTenantsByDevEuis.mockResolvedValue(new Map())
  service.enqueue(makeReading(1))
  await service.flush()
  expect(mocks.insertTelemetryBatch).not.toHaveBeenCalled()
  expect(mocks.upsertDevices).not.toHaveBeenCalled()
})
```

- [ ] **Step 5: Rodar testes e typecheck**

Run (from `platform/backend`):

```bash
npx vitest run test/persistService.test.ts && npm run typecheck
```

Expected: PASS e typecheck OK (após Task 12 definir `resolveTenantsByDevEuis`).

- [ ] **Step 6: Commit**

```bash
git add platform/backend/src/repositories/telemetryRepository.ts platform/backend/src/services/persistService.ts platform/backend/src/types.ts platform/backend/test/persistService.test.ts
git commit -m "feat(backend): telemetryRepository e ingestão MQTT tenant-aware"
```

---

## Task 12 (Issue #11): deviceRepository tenant-aware

**Files:**
- Modify: `platform/backend/src/repositories/deviceRepository.ts`

- [ ] **Step 1: Atualizar o repositório**

`platform/backend/src/repositories/deviceRepository.ts`:

```ts
import { pool } from '../db/pool'
import type { Reading } from '../types'

export interface DeviceRow {
  device_eui: string
  device_name: string
  application_id: string
  tenant_id: string
  last_seen_at: string
  last_rssi: number | null
  last_snr: number | null
  created_at: string
}

export interface DeviceStatusRow extends DeviceRow {
  online: boolean
}

export interface ListDevicesQuery {
  tenantId: string
}

const DEVICE_COLUMNS = 7

export async function upsertDevices(readings: Reading[]): Promise<void> {
  const valid = readings.filter((r) => r.tenantId)
  if (valid.length === 0) return
  const values: unknown[] = []
  const rows: unknown[][] = []
  for (const r of valid) {
    rows.push([r.deviceEui, r.tenantId!, r.deviceName, r.applicationId, r.timestamp, r.rssi ?? null, r.snr ?? null])
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
    `INSERT INTO devices (device_eui, tenant_id, device_name, application_id, last_seen_at, last_rssi, last_snr)
     VALUES ${placeholders}
     ON CONFLICT (device_eui) DO UPDATE SET
       tenant_id = EXCLUDED.tenant_id,
       device_name = EXCLUDED.device_name,
       application_id = EXCLUDED.application_id,
       last_seen_at = EXCLUDED.last_seen_at,
       last_rssi = EXCLUDED.last_rssi,
       last_snr = EXCLUDED.last_snr`,
    values
  )
}

export async function listDevices(q: ListDevicesQuery): Promise<DeviceStatusRow[]> {
  const result = await pool.query<DeviceStatusRow>(
    `SELECT device_eui, device_name, application_id, tenant_id, last_seen_at, last_rssi, last_snr, created_at,
            (last_seen_at > NOW() - make_interval(mins => $2)) AS online
     FROM devices
     WHERE tenant_id = $1
     ORDER BY last_seen_at DESC`,
    [q.tenantId, 5]
  )
  return result.rows
}

export async function resolveTenantsByDevEuis(devEuis: string[]): Promise<Map<string, string>> {
  if (devEuis.length === 0) return new Map()
  const result = await pool.query<{ device_eui: string; tenant_id: string }>(
    `SELECT device_eui, tenant_id FROM devices WHERE device_eui = ANY($1::text[])`,
    [devEuis]
  )
  return new Map(result.rows.map((r) => [r.deviceEui, r.tenant_id]))
}
```

Observação: `listDevices` usa `OFFLINE_THRESHOLD_MINUTES` fixo `5` por simplicidade; melhor usar env:

```ts
import { env } from '../config/env'
// ...
(last_seen_at > NOW() - make_interval(mins => $2)) AS online
// params: [q.tenantId, env.OFFLINE_THRESHOLD_MINUTES]
```

- [ ] **Step 2: Rodar typecheck**

Run (from `platform/backend`):

```bash
npm run typecheck
```

Expected: OK (routes já chamam `listDevices({ tenantId })`; `upsertDevices`/`resolveTenantsByDevEuis` usados pelo persistService).

- [ ] **Step 3: Commit**

```bash
git add platform/backend/src/repositories/deviceRepository.ts
git commit -m "feat(backend): deviceRepository tenant-aware com resolveTenantsByDevEuis"
```

---

## Task 13 (Issue #12): alertRepository tenant-aware

**Files:**
- Modify: `platform/backend/src/repositories/alertRepository.ts`
- Modify: `platform/backend/src/services/thresholdEngine.ts`
- Modify: `platform/backend/test/thresholdEngine.test.ts`

- [ ] **Step 1: Atualizar o repositório**

`platform/backend/src/repositories/alertRepository.ts`:

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

export async function canAlert(tenantId: string, deviceEui: string, metric: string): Promise<boolean> {
  const result = await pool.query<{ can: boolean }>(
    `SELECT NOT EXISTS (
       SELECT 1 FROM alerts
       WHERE tenant_id = $1 AND device_eui = $2 AND metric = $3 AND cooldown_until > NOW()
     ) AS can`,
    [tenantId, deviceEui, metric]
  )
  return result.rows[0]?.can ?? true
}

export async function registerAlert(
  tenantId: string,
  deviceEui: string,
  metric: string,
  value: number,
  threshold: number,
  channel: string,
  cooldownMinutes: number
): Promise<void> {
  await pool.query(
    `INSERT INTO alerts (tenant_id, device_eui, metric, value, threshold, channel, cooldown_until)
     VALUES ($1, $2, $3, $4, $5, $6, NOW() + make_interval(mins => $7))`,
    [tenantId, deviceEui, metric, value, threshold, channel, cooldownMinutes]
  )
}

export interface ListAlertsQuery {
  tenantId: string
  limit: number
  offset: number
}

export async function listAlerts(
  q: ListAlertsQuery
): Promise<{ rows: AlertRow[]; total: number }> {
  const count = await pool.query<{ count: string }>(
    `SELECT COUNT(*)::text AS count FROM alerts WHERE tenant_id = $1`,
    [q.tenantId]
  )
  const result = await pool.query<AlertRow>(
    `SELECT id, device_eui, metric, value, threshold, channel, sent_at, cooldown_until
     FROM alerts
     WHERE tenant_id = $1
     ORDER BY sent_at DESC
     LIMIT $2 OFFSET $3`,
    [q.tenantId, q.limit, q.offset]
  )
  return { rows: result.rows, total: Number(count.rows[0]?.count ?? 0) }
}
```

A tabela `alerts` já possui a coluna `tenant_id` e os índices criados no `init.sql` (Task 5). Nenhuma alteração de schema é necessária nesta task.

- [ ] **Step 2: Atualizar o thresholdEngine**

`platform/backend/src/services/thresholdEngine.ts`:

```ts
if (!(await canAlert(reading.tenantId ?? '', reading.deviceEui, rule.metric))) continue
await registerAlert(
  reading.tenantId ?? '',
  reading.deviceEui,
  rule.metric,
  value,
  rule.value,
  'all',
  env.ALERT_COOLDOWN_MINUTES
)
```

Adicione também uma guarda no início de `process`:

```ts
if (!reading.tenantId) return
```

- [ ] **Step 3: Atualizar testes de thresholdEngine**

Em `platform/backend/test/thresholdEngine.test.ts`:
- `makeReading` ganha `tenantId: 'tenant-1'`.
- Assert de `registerAlert` passa a ser `'tenant-1', 'eui-1', 'ldr_value', 600, 500, expect.any(String), 5`.
- Adicione um teste de cooldown isolado por tenant:

```ts
it('não dispara alerta quando tenantId ausente', async () => {
  const engine = new ThresholdEngine(sender, RULES)
  const reading = makeReading({ ldr_value: 900 })
  delete (reading as { tenantId?: string }).tenantId
  await engine.process(reading)
  expect(sender.send).not.toHaveBeenCalled()
})
```

- [ ] **Step 4: Rodar testes e typecheck**

Run (from `platform/backend`):

```bash
npx vitest run test/thresholdEngine.test.ts test/isolation.test.ts && npm run typecheck
```

Expected: PASS e typecheck OK.

- [ ] **Step 5: Commit**

```bash
git add platform/backend/src/repositories/alertRepository.ts platform/backend/src/services/thresholdEngine.ts platform/backend/src/db/init.sql platform/backend/test/thresholdEngine.test.ts
git commit -m "feat(backend): alertRepository e motor de thresholds tenant-aware"
```

---

## Task 14 (Issue #14): Testes de auth, middleware e isolamento

**Files:**
- Modify: `platform/backend/test/env.test.ts`
- Modify: `platform/backend/test/persistService.test.ts`
- Modify: `platform/backend/test/thresholdEngine.test.ts`
- Create: `platform/backend/test/parser.test.ts` (inalterado — verificar)

- [ ] **Step 1: Rodar a suíte completa**

Run (from `platform/backend`):

```bash
npm test
```

Expected: TODAS as suítes passam:
- `env.test.ts` (defaults JWT/ChirpStack)
- `parser.test.ts`
- `rules.test.ts`
- `thresholdEngine.test.ts` (tenant-aware)
- `persistService.test.ts` (tenant resolution + descarte)
- `authService.test.ts` (register/login)
- `middlewareAuth.test.ts`
- `isolation.test.ts`
- `dashboardTemplates.test.ts`

Se alguma falhar, corrija a assinatura/mock apontado. Atenção: o `parser` não muda — confirme que `parser.test.ts` segue verde.

- [ ] **Step 2: Rodar typecheck e build**

Run:

```bash
npm run typecheck && npm run build
```

Expected: typecheck OK; build gera `dist/` com `dist/db/init.sql`.

- [ ] **Step 3: Verificação manual opcional (Docker)**

Se o ambiente Docker estiver disponível:

```bash
docker compose -f platform/docker-compose.yml up --build -d
curl -s http://localhost:4000/api/health
curl -s -X POST http://localhost:4000/api/auth/register -H 'Content-Type: application/json' -d '{"tenantName":"Teste","email":"a@b.com","password":"senha-forte-123"}'
```

Expected: health `{"status":"ok",...}`; register retorna `201` com `token` e `user`.

- [ ] **Step 4: Commit**

```bash
git add platform/backend/test
git commit -m "test(backend): suíte de auth, middleware e isolamento por tenant"
```

---

## Self-Review (executado antes de entregar)

1. **Cobertura do spec (Etapa 1 PRD):**
   - Migrations Prisma (Tenants, Users, Devices, Dashboards) → Tasks 1-3.
   - Serviços de Auth (JWT, Register, Login) → Tasks 7-8.
   - Env `CHIRPSTACK_API_KEY` → Task 4.
   - Isolamento por `tenant_id` em todas as queries → Tasks 10-13.
   - RF05 (dashboard padrão LDR/Bateria no onboarding) → Task 6 + register.
2. **Placeholders:** todas as etapas contêm código/arquivo/URL exatos.
3. **Consistência de tipos:** `Reading.tenantId?: string`; repositories aceitam `tenantId`; rotas usam `req.auth!.tenantId`; `resolveTenantsByDevEuis` retorna `Map<string,string>`.
