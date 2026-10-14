# Dashboard WebSocket Real-time Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar o dashboard (`/dashboard/:appId`) ao WebSocket `WS /ws/telemetry/{app_id}` do `telemetry_consumer` e atualizar o gráfico de telemetria em tempo real (≤ 2s), sem refresh.

**Architecture:** Um hook `useTelemetrySocket` abre uma conexão WebSocket por `appId` e entrega cada evento validado a um callback; o `Dashboard` anexa os eventos ao estado local (`liveItems`), deduplicando por `(dev_eui, time, event_type)`, e mescla esse estado com o histórico REST já carregado antes de derivar as séries do gráfico. Helpers puros de URL, parsing e merge ficam em `services/telemetry.ts`.

**Tech Stack:** React 19 · TypeScript · Vite · Recharts 2 · Vitest + Testing Library + MSW 2 · WebSocket nativo · nginx.

**Spec:** `docs/superpowers/specs/2026-10-12-dashboard-websocket-realtime-design.md`

## Global Constraints

- Todo o código do dashboard fica em `client/frontend/`.
- Contrato da mensagem = `TelemetryItem`: `{ time, app_id, dev_eui, event_type, payload, rssi, snr }`.
- Caminho do WebSocket: `/ws/telemetry/{appId}`; `appId` = parâmetro da rota `/dashboard/:appId` = `APP_ID` do `telemetry_consumer`.
- Chave de deduplicação: `(dev_eui, time, event_type)`.
- Sem reconexão automática (issue #100), sem polling fallback (issue #44), sem auth no WebSocket.
- Cobertura mínima global: 70% (`client/frontend/vitest.config.ts`).
- Comandos do frontend rodam em `client/frontend/`: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npx vitest run --coverage`, `npm run build`.
- `mocks/**` é excluído da cobertura.

## Review Focus

- Evento com `app_id` diferente do `appId` da rota deve ser ignorado, nunca plotado.
- Evento de um `dev_eui` não selecionado deve ser ignorado quando um device específico está selecionado, e aceito no modo "Todos os devices".
- Evento repetido (mesmo `dev_eui`/`time`/`event_type`) não pode duplicar o ponto no gráfico.
- JSON inválido ou com campos essenciais ausentes não pode quebrar a tela nem chamar o callback.
- Desmontar o componente ou trocar de `appId` deve fechar o WebSocket anterior (inclusive sob `React.StrictMode`, que monta o efeito duas vezes em dev).

---

### Task 1: Helpers de URL, parsing e deduplicação

**Files:**
- Modify: `client/frontend/src/services/telemetry.ts`
- Test: `client/frontend/src/services/telemetry.test.ts`

**Interfaces:**
- Consumes: `TelemetryItem` (já existente no mesmo arquivo).
- Produces:
  - `buildTelemetrySocketUrl(appId: string): string`
  - `parseTelemetryMessage(raw: unknown): TelemetryItem | null`
  - `appendItem(items: TelemetryItem[], item: TelemetryItem): TelemetryItem[]`

- [ ] **Step 1: Write the failing tests**

Adicionar a `client/frontend/src/services/telemetry.test.ts`:

```ts
import {
  buildTelemetrySocketUrl,
  parseTelemetryMessage,
  appendItem,
} from './telemetry';

describe('buildTelemetrySocketUrl', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('uses VITE_WS_URL as base when defined', () => {
    vi.stubEnv('VITE_WS_URL', 'wss://ws.example.com');
    expect(buildTelemetrySocketUrl('app-1')).toBe(
      'wss://ws.example.com/ws/telemetry/app-1',
    );
  });

  it('derives wss from https location', () => {
    vi.stubEnv('VITE_WS_URL', '');
    vi.stubGlobal('location', { protocol: 'https:', host: 'linx.test' });
    expect(buildTelemetrySocketUrl('app-2')).toBe(
      'wss://linx.test/ws/telemetry/app-2',
    );
  });

  it('derives ws from http location', () => {
    vi.stubEnv('VITE_WS_URL', '');
    vi.stubGlobal('location', { protocol: 'http:', host: 'localhost:5173' });
    expect(buildTelemetrySocketUrl('app-3')).toBe(
      'ws://localhost:5173/ws/telemetry/app-3',
    );
  });
});

describe('parseTelemetryMessage', () => {
  it('parses a valid JSON string into a TelemetryItem', () => {
    const raw =
      '{"time":"2026-01-01T00:00:00Z","dev_eui":"aabb","payload":{"temperature":21},"rssi":-70,"snr":7,"app_id":"app-1","event_type":"up"}';
    expect(parseTelemetryMessage(raw)).toEqual({
      time: '2026-01-01T00:00:00Z',
      dev_eui: 'aabb',
      payload: { temperature: 21 },
      rssi: -70,
      snr: 7,
      app_id: 'app-1',
      event_type: 'up',
    });
  });

  it('returns null on invalid JSON', () => {
    expect(parseTelemetryMessage('{not json')).toBeNull();
  });

  it('returns null when a required field is missing', () => {
    expect(parseTelemetryMessage('{"dev_eui":"aabb","payload":{}}')).toBeNull();
    expect(parseTelemetryMessage('{"time":"t","payload":{}}')).toBeNull();
    expect(parseTelemetryMessage('{"time":"t","dev_eui":"aabb"}')).toBeNull();
  });

  it('defaults optional fields when absent', () => {
    expect(
      parseTelemetryMessage('{"time":"t","dev_eui":"aabb","payload":{}}'),
    ).toEqual({
      time: 't',
      dev_eui: 'aabb',
      payload: {},
      rssi: null,
      snr: null,
      app_id: '',
      event_type: '',
    });
  });
});

describe('appendItem', () => {
  const point = (time: string, devEui = 'aabb', eventType = 'up') => ({
    time,
    dev_eui: devEui,
    payload: { temperature: 1 },
    rssi: null,
    snr: null,
    app_id: 'app-1',
    event_type: eventType,
  });

  it('appends a new item sorted by time', () => {
    const items = [point('2026-01-02T00:00:00Z')];
    const result = appendItem(items, point('2026-01-01T00:00:00Z'));
    expect(result.map((i) => i.time)).toEqual([
      '2026-01-01T00:00:00Z',
      '2026-01-02T00:00:00Z',
    ]);
  });

  it('ignores a duplicate by (dev_eui, time, event_type)', () => {
    const items = [point('2026-01-01T00:00:00Z')];
    const result = appendItem(items, point('2026-01-01T00:00:00Z'));
    expect(result).toHaveLength(1);
    expect(result).toBe(items);
  });

  it('keeps different event_type at the same time', () => {
    const items = [point('2026-01-01T00:00:00Z', 'aabb', 'up')];
    const result = appendItem(items, point('2026-01-01T00:00:00Z', 'aabb', 'status'));
    expect(result).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/services/telemetry.test.ts`
Expected: FAIL — `buildTelemetrySocketUrl`/`parseTelemetryMessage`/`appendItem` não exportados.

- [ ] **Step 3: Implement the helpers**

Em `client/frontend/src/services/telemetry.ts`, adicionar:

```ts
/** URL absoluta do WebSocket de telemetria para o app. */
export function buildTelemetrySocketUrl(appId: string): string {
  const base = import.meta.env.VITE_WS_URL;
  const prefix =
    base && base.trim() !== ''
      ? base.replace(/\/$/, '')
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
  return `${prefix}/ws/telemetry/${appId}`;
}

/** Valida e normaliza uma mensagem recebida do WebSocket. */
export function parseTelemetryMessage(raw: unknown): TelemetryItem | null {
  let data: unknown = raw;
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (typeof data !== 'object' || data === null) return null;
  const record = data as Record<string, unknown>;
  const { time, dev_eui, payload } = record;
  if (typeof time !== 'string' || typeof dev_eui !== 'string') return null;
  if (typeof payload !== 'object' || payload === null) return null;
  return {
    time,
    dev_eui,
    payload: payload as Record<string, unknown>,
    rssi: typeof record.rssi === 'number' ? record.rssi : null,
    snr: typeof record.snr === 'number' ? record.snr : null,
    app_id: typeof record.app_id === 'string' ? record.app_id : '',
    event_type: typeof record.event_type === 'string' ? record.event_type : '',
  };
}

/** Anexa um item deduplicando por (dev_eui, time, event_type), ordenado por time. */
export function appendItem(
  items: TelemetryItem[],
  item: TelemetryItem,
): TelemetryItem[] {
  const exists = items.some(
    (current) =>
      current.dev_eui === item.dev_eui &&
      current.time === item.time &&
      current.event_type === item.event_type,
  );
  if (exists) return items;
  return [...items, item].sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/services/telemetry.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add client/frontend/src/services/telemetry.ts client/frontend/src/services/telemetry.test.ts
git commit -m "feat(frontend): helpers de URL, parsing e dedupe do WebSocket"
```

---

### Task 2: Hook `useTelemetrySocket`

**Files:**
- Create: `client/frontend/src/hooks/useTelemetrySocket.ts`
- Test: `client/frontend/src/hooks/useTelemetrySocket.test.tsx`

**Interfaces:**
- Consumes: `buildTelemetrySocketUrl`, `parseTelemetryMessage` (Task 1).
- Produces: `useTelemetrySocket(appId: string, onMessage: (item: TelemetryItem) => void): void`.

- [ ] **Step 1: Write the failing tests**

Criar `client/frontend/src/hooks/useTelemetrySocket.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { useTelemetrySocket } from './useTelemetrySocket';
import type { TelemetryItem } from '../services/telemetry';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
}

function Probe({
  appId,
  onMessage,
}: {
  appId: string;
  onMessage: (item: TelemetryItem) => void;
}) {
  useTelemetrySocket(appId, onMessage);
  return null;
}

describe('useTelemetrySocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.stubGlobal('location', { protocol: 'http:', host: 'localhost' });
  });

  afterEach(() => vi.unstubAllGlobals());

  it('opens the socket at /ws/telemetry/{appId}', () => {
    render(<Probe appId="app-1" onMessage={vi.fn()} />);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe(
      'ws://localhost/ws/telemetry/app-1',
    );
  });

  it('delivers a parsed item to the callback', () => {
    const onMessage = vi.fn();
    render(<Probe appId="app-1" onMessage={onMessage} />);
    FakeWebSocket.instances[0].onmessage?.({
      data: '{"time":"t","dev_eui":"aabb","payload":{}}',
    });
    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ time: 't', dev_eui: 'aabb' }),
    );
  });

  it('ignores invalid JSON without calling the callback', () => {
    const onMessage = vi.fn();
    render(<Probe appId="app-1" onMessage={onMessage} />);
    FakeWebSocket.instances[0].onmessage?.({ data: '{not json' });
    expect(onMessage).not.toHaveBeenCalled();
  });

  it('closes the socket on unmount', () => {
    const { unmount } = render(<Probe appId="app-1" onMessage={vi.fn()} />);
    const socket = FakeWebSocket.instances[0];
    unmount();
    expect(socket.close).toHaveBeenCalled();
  });

  it('reopens with a new url when appId changes', () => {
    const { rerender } = render(<Probe appId="app-1" onMessage={vi.fn()} />);
    const first = FakeWebSocket.instances[0];

    rerender(<Probe appId="app-2" onMessage={vi.fn()} />);

    expect(first.close).toHaveBeenCalled();
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].url).toBe(
      'ws://localhost/ws/telemetry/app-2',
    );
  });

  it('does not throw when the socket errors', () => {
    render(<Probe appId="app-1" onMessage={vi.fn()} />);
    expect(() => FakeWebSocket.instances[0].onerror?.()).not.toThrow();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/hooks/useTelemetrySocket.test.tsx`
Expected: FAIL — módulo não encontrado.

- [ ] **Step 3: Implement the hook**

Criar `client/frontend/src/hooks/useTelemetrySocket.ts`:

```ts
import { useEffect, useRef } from 'react';
import {
  buildTelemetrySocketUrl,
  parseTelemetryMessage,
  type TelemetryItem,
} from '../services/telemetry';

export function useTelemetrySocket(
  appId: string,
  onMessage: (item: TelemetryItem) => void,
): void {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!appId) return;
    const ws = new WebSocket(buildTelemetrySocketUrl(appId));
    ws.onmessage = (event) => {
      const item = parseTelemetryMessage(event.data);
      if (item) onMessageRef.current(item);
    };
    ws.onerror = () => {};
    return () => ws.close();
  }, [appId]);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/hooks/useTelemetrySocket.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add client/frontend/src/hooks/useTelemetrySocket.ts client/frontend/src/hooks/useTelemetrySocket.test.tsx
git commit -m "feat(frontend): hook useTelemetrySocket para stream de telemetria"
```

---

### Task 3: Wiring no Dashboard

**Files:**
- Modify: `client/frontend/src/pages/dashboard/Dashboard.tsx`
- Test: `client/frontend/src/pages/dashboard/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `useTelemetrySocket` (Task 2), `appendItem` (Task 1), `TelemetryItem`.
- Produces: nada (página).

- [ ] **Step 1: Write the failing tests**

Em `client/frontend/src/pages/dashboard/Dashboard.test.tsx`, adicionar `vi` ao
import já existente de `vitest` e `act` ao import de `@testing-library/react`,
e mockar o hook no topo do módulo:

```tsx
import { useTelemetrySocket } from '../../hooks/useTelemetrySocket';

vi.mock('../../hooks/useTelemetrySocket', () => ({
  useTelemetrySocket: vi.fn(),
}));
```

e adicionar um `describe`:

```tsx
describe('Dashboard real-time (WebSocket)', () => {
  function captureSocket() {
    let emit: (item: unknown) => void = () => {};
    vi.mocked(useTelemetrySocket).mockImplementation((_appId, onMessage) => {
      emit = onMessage as (item: unknown) => void;
    });
    return () => emit;
  }

  it('updates the chart and last reading without a new REST call', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff1111');
    const getEmit = captureSocket();

    let telemetryCalls = 0;
    server.use(
      http.get('*/api/v1/telemetry', () => {
        telemetryCalls += 1;
        return HttpResponse.json({
          items: [
            {
              time: '2026-01-01T00:00:00Z',
              dev_eui: 'aabbccddeeff1111',
              payload: { temperature: 20 },
              rssi: -70,
              snr: 7,
              app_id: appId,
              event_type: 'up',
            },
          ],
          next_cursor: null,
        });
      }),
    );

    renderDashboard(appId);
    await screen.findByTestId('telemetry-chart');
    const callsAfterLoad = telemetryCalls;

    act(() => {
      getEmit()({
        time: '2026-01-01T00:05:00Z',
        dev_eui: 'aabbccddeeff1111',
        payload: { temperature: 25 },
        rssi: -70,
        snr: 7,
        app_id: appId,
        event_type: 'up',
      });
    });

    const expected = `Última leitura: ${formatDate('2026-01-01T00:05:00Z')}`;
    expect(await screen.findByText(expected)).toBeInTheDocument();
    expect(telemetryCalls).toBe(callsAfterLoad);
  });

  it('ignores a live event from another app', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff1212');
    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );
    const getEmit = captureSocket();
    renderDashboard(appId);
    await screen.findByLabelText('Device');

    act(() => {
      getEmit()({
        time: '2099-02-02T00:00:00Z',
        dev_eui: 'aabbccddeeff1212',
        payload: { temperature: 99 },
        rssi: -70,
        snr: 7,
        app_id: 'outro-app',
        event_type: 'up',
      });
    });

    const notExpected = `Última leitura: ${formatDate('2099-02-02T00:00:00Z')}`;
    expect(screen.queryByText(notExpected)).not.toBeInTheDocument();
  });

  it('ignores a live event from another device when one is selected', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff1313');
    await createDevice(appId, 'aabbccddeeff1414');
    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );
    const getEmit = captureSocket();
    renderDashboard(appId);
    await screen.findByLabelText('Device');

    act(() => {
      getEmit()({
        time: '2099-03-03T00:00:00Z',
        dev_eui: 'aabbccddeeff1414',
        payload: { temperature: 99 },
        rssi: -70,
        snr: 7,
        app_id: appId,
        event_type: 'up',
      });
    });

    const notExpected = `Última leitura: ${formatDate('2099-03-03T00:00:00Z')}`;
    expect(screen.queryByText(notExpected)).not.toBeInTheDocument();
  });

  it('accepts a live event from any device in Todos mode', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff1515');
    await createDevice(appId, 'aabbccddeeff1616');
    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );
    const getEmit = captureSocket();
    renderDashboard(appId);
    await screen.findByLabelText('Device');

    await userEvent.selectOptions(
      screen.getByLabelText('Device'),
      'Todos os devices',
    );

    act(() => {
      getEmit()({
        time: '2099-04-04T00:00:00Z',
        dev_eui: 'aabbccddeeff1616',
        payload: { temperature: 30 },
        rssi: -70,
        snr: 7,
        app_id: appId,
        event_type: 'up',
      });
    });

    const expected = `Última leitura: ${formatDate('2099-04-04T00:00:00Z')}`;
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });
});
```

> Nota: os eventos de teste usam `app_id: appId` (o UUID da aplicação devolvido
> por `firstAppId()`), de modo que o evento de "outro app" usa um valor
> claramente diferente.

Adicionar `act` ao import de `@testing-library/react`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- src/pages/dashboard/Dashboard.test.tsx`
Expected: FAIL — o gráfico não reflete o evento (hook ainda real/inexistente no wiring).

- [ ] **Step 3: Wire the hook and merge live items**

Em `client/frontend/src/pages/dashboard/Dashboard.tsx`:

Adicionar imports:

```tsx
import { useEffect, useState } from 'react';
import { appendItem, type TelemetryItem } from '../../services/telemetry';
import { useTelemetrySocket } from '../../hooks/useTelemetrySocket';
```

Após o cálculo de `devices`/`activeDevEui` (antes do `useAsyncData` da história), adicionar o estado e a assinatura do socket:

```tsx
const [liveItems, setLiveItems] = useState<TelemetryItem[]>([]);

useEffect(() => {
  setLiveItems([]);
}, [appId]);

useTelemetrySocket(appId, (item) => {
  if (item.app_id && item.app_id !== appId) return;
  setLiveItems((previous) => appendItem(previous, item));
});
```

Substituir o bloco que hoje deriva `items`/`metrics`/`chartSeries` por uma versão que mescla o histórico com `liveItems`. Manter a assinatura `DeviceHistory` já existente:

```tsx
const entries = history ?? [];

const liveByDevEui = new Map<string, TelemetryItem[]>();
for (const item of liveItems) {
  const bucket = liveByDevEui.get(item.dev_eui);
  if (bucket) bucket.push(item);
  else liveByDevEui.set(item.dev_eui, [item]);
}

const combinedEntries: DeviceHistory[] = entries.map((entry) => {
  const live = liveByDevEui.get(entry.devEui) ?? [];
  return {
    devEui: entry.devEui,
    history: {
      next_cursor: entry.history.next_cursor,
      items: live.reduce(
        (acc, item) => appendItem(acc, item),
        entry.history.items,
      ),
    },
  };
});

const items = combinedEntries.flatMap((entry) => entry.history.items);
const metrics = numericMetrics(items);
const activeMetric = metrics.includes(metric) ? metric : (metrics[0] ?? '');
```

Atualizar as referências a `entries` no cálculo do `chartSeries` para `combinedEntries` (mantendo `items` como acima):

```tsx
const chartSeries: SeriesInput[] =
  activeDevEui === ALL_DEVICES
    ? combinedEntries.map((entry) => ({
        key: entry.devEui,
        label: labelFor(entry.devEui),
        data: buildSeries(entry.history.items, activeMetric),
      }))
    : [
        {
          key: activeDevEui,
          label: labelFor(activeDevEui),
          data: buildSeries(items, activeMetric),
        },
      ];
```

Não alterar o comportamento de erro/loading do histórico REST.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/pages/dashboard/Dashboard.test.tsx`
Expected: PASS (novos e existentes).

- [ ] **Step 5: Commit**

```bash
git add client/frontend/src/pages/dashboard/Dashboard.tsx client/frontend/src/pages/dashboard/Dashboard.test.tsx
git commit -m "feat(frontend): dashboard atualiza em tempo real via WebSocket"
```

---

### Task 4: Proxy de dev, rota nginx e mock MSW

**Files:**
- Modify: `client/frontend/vite.config.ts`
- Modify: `client/frontend/nginx.conf`
- Modify: `client/frontend/Dockerfile`
- Modify: `client/docker-compose.yml`
- Modify: `client/.env.example`
- Create: `client/frontend/src/mocks/websocket.ts`
- Modify: `client/frontend/src/mocks/browser.ts`

**Interfaces:**
- Produces: handler MSW `telemetrySocket` (exportado), rota nginx `/ws/`, env `WS_BACKEND_URL`, proxy Vite `/ws`.

- [ ] **Step 1: Add the dev proxy**

Em `client/frontend/vite.config.ts`, adicionar o proxy `/ws` com `ws: true` ao lado do `/api`:

```ts
      '/ws': {
        target: process.env.VITE_WS_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
```

- [ ] **Step 2: Add the nginx `/ws/` route and the Docker env**

Em `client/frontend/nginx.conf`, antes do fallback do SPA (`location /`), adicionar:

```nginx
    # WebSocket de telemetria: encaminha para ${WS_BACKEND_URL} preservando o upgrade.
    location /ws/ {
        proxy_pass ${WS_BACKEND_URL};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```

Em `client/frontend/Dockerfile`, ao lado de `ENV BACKEND_URL=...`, adicionar:

```dockerfile
ENV WS_BACKEND_URL=http://127.0.0.1:8000
```

- [ ] **Step 3: Wire the client compose and env**

Em `client/docker-compose.yml`, no serviço `frontend`, adicionar `WS_BACKEND_URL` ao `environment`:

```yaml
      - WS_BACKEND_URL=${WS_BACKEND_URL:-http://telemetry_consumer:8000}
```

Em `client/.env.example`, adicionar abaixo de `BACKEND_URL`:

```bash
# Destino do proxy /ws do nginx (WebSocket de telemetria do telemetry_consumer).
WS_BACKEND_URL=http://telemetry_consumer:8000
```

- [ ] **Step 4: Add the MSW WebSocket mock**

Criar `client/frontend/src/mocks/websocket.ts`:

```ts
import { ws } from 'msw';

export const telemetrySocket = ws.link('*/ws/telemetry/:appId');

export const websocketHandlers = [
  telemetrySocket.addEventListener('connection', ({ client }) => {
    const timer = setInterval(() => {
      client.send(
        JSON.stringify({
          time: new Date().toISOString(),
          dev_eui: 'aabbccddeeff0000',
          payload: { temperature: 20 + Math.random() * 5 },
          rssi: -70,
          snr: 7,
          app_id: 'mock-app',
          event_type: 'up',
        }),
      );
    }, 2000);
    client.addEventListener('close', () => clearInterval(timer));
  }),
];
```

Em `client/frontend/src/mocks/browser.ts`, registrar os handlers de WebSocket:

```ts
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';
import { websocketHandlers } from './websocket';

export const worker = setupWorker(...handlers, ...websocketHandlers);
```

Manter `handlers.ts` (usado por `setupServer` nos testes) sem os handlers de WebSocket.

- [ ] **Step 5: Verify build and compose**

Run:
```bash
cd client/frontend && npm run build
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx && python3 -c "import yaml; d=yaml.safe_load(open('client/docker-compose.yml')); print(d['services']['frontend']['environment'])"
```
Expected: build OK; environment inclui `WS_BACKEND_URL=${WS_BACKEND_URL:-http://telemetry_consumer:8000}`.

- [ ] **Step 6: Commit**

```bash
git add client/frontend/vite.config.ts client/frontend/nginx.conf client/frontend/Dockerfile client/docker-compose.yml client/.env.example client/frontend/src/mocks/websocket.ts client/frontend/src/mocks/browser.ts
git commit -m "feat(frontend): proxy /ws, mock de WebSocket e backend do stream"
```

---

### Task 5: Documentação

**Files:**
- Modify: `client/frontend/README.md`
- Modify: `client/README.md`
- Modify: `docs/client/README.md` (espelho do anterior)

**Interfaces:**
- Consumes: comportamento das Tasks 1–4.
- Produces: nada (docs).

- [ ] **Step 1: Update the frontend README**

Em `client/frontend/README.md`, na seção "Dashboard de Telemetria", adicionar um parágrafo "Tempo real (WebSocket)" e ajustar a tabela de variáveis/stack:

- Descrever que o dashboard abre `WS /ws/telemetry/{app_id}` ao montar, aplica cada evento ao gráfico em ≤ 2s e fecha a conexão no unmount ou troca de aplicação; eventos de outro app/device são ignorados.
- Adicionar à tabela de variáveis: `VITE_WS_URL` (default vazio → same-origin), e `VITE_WS_PROXY_TARGET` (target do proxy `/ws` de dev).
- Mencionar o proxy `/ws` no dev server e o mock MSW de WebSocket quando `VITE_ENABLE_MOCKS=true`.

- [ ] **Step 2: Update the client READMEs**

Em `client/README.md`, na seção "Frontend (dashboard)", acrescentar que o dashboard também consome o stream `WS /ws/telemetry/{app_id}` em tempo real. Copiar o arquivo para o espelho:

```bash
cp client/README.md docs/client/README.md
```

- [ ] **Step 3: Verify the docs build and mirror**

Run:
```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Lynx && diff -q client/README.md docs/client/README.md && poetry run mkdocs build --strict
```
Expected: arquivos idênticos; MkDocs sem warnings.

- [ ] **Step 4: Commit**

```bash
git add client/frontend/README.md client/README.md docs/client/README.md
git commit -m "docs(frontend): documenta dashboard em tempo real via WebSocket"
```

---

## Verificação final

- [ ] `cd client/frontend && npm run lint && npx tsc --noEmit && npx vitest run --coverage` — testes passam e cobertura ≥ 70%.
- [ ] `cd client/frontend && npm run build` — build OK.
- [ ] `poetry run mkdocs build --strict` — docs sem warnings.
- [ ] Verificação manual (depende do roteamento de infra, ver limitações): com o stack do cliente no ar, publicar um uplink via MQTT e ver o ponto aparecer no gráfico em ≤ 2s sem refresh.

## Limitações conhecidas (fora deste plano)

- Roteamento `/ws` no `deploy/nginx/nginx.conf` (unificado) e a rota REST `/api/v1/telemetry` até o `telemetry_consumer` seguem pendentes (issue de infra/#42).
- Reconexão (issue #100) e polling fallback (issue #44) não fazem parte deste plano.
