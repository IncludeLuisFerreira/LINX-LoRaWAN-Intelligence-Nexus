import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { handlers } from './handlers';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function post(url: string, body: unknown) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function firstTenantId(): Promise<string> {
  const res = await fetch(`${base}/tenant`);
  const tenants = (await res.json()) as { id: string }[];
  return tenants[0].id;
}

async function firstAppId(): Promise<string> {
  const tenantId = await firstTenantId();
  const res = await fetch(`${base}/tenant/${tenantId}/applications`);
  const apps = (await res.json()) as { id: string }[];
  return apps[0].id;
}

const validDevice = (appId: string, devEui: string) => ({
  dev_eui: devEui,
  app_id: appId,
  join_eui: '1122334455667788',
  app_key: '00112233445566778899aabbccddeeff',
});

describe('tenant handlers', () => {
  it('serves GET /tenant and returns UUID ids', async () => {
    const res = await fetch(`${base}/tenant`);
    const tenants = (await res.json()) as { id: string }[];

    expect(res.status).toBe(200);
    expect(tenants.length).toBeGreaterThan(0);
    for (const tenant of tenants) expect(tenant.id).toMatch(UUID_RE);
  });

  it('accepts POST /tenant/ (trailing slash) and returns 201 + Location', async () => {
    const res = await post(`${base}/tenant/`, { name: 'Novo Tenant' });
    const body = (await res.json()) as { id: string; description: string };

    expect(res.status).toBe(201);
    expect(body.description).toBe('');
    expect(body.id).toMatch(UUID_RE);
    expect(res.headers.get('Location')).toBe(`${base}/tenant/${body.id}`);
  });

  it('returns 404 with detail for an unknown tenant', async () => {
    const res = await fetch(`${base}/tenant/${crypto.randomUUID()}`);
    const body = (await res.json()) as { detail: string };

    expect(res.status).toBe(404);
    expect(body.detail).toBe('Tenant not found!');
  });
});

describe('application handlers', () => {
  it('creates an app under a tenant with 201 + Location and a UUID id', async () => {
    const tenantId = await firstTenantId();
    const res = await post(`${base}/tenant/${tenantId}/applications`, {
      name: 'Nova App',
    });
    const body = (await res.json()) as { id: string; description: string };

    expect(res.status).toBe(201);
    expect(body.id).toMatch(UUID_RE);
    expect(body.description).toBe('');
    expect(res.headers.get('Location')).toBe(
      `${base}/tenant/${tenantId}/applications/${body.id}`,
    );
  });

  it('rejects clearing description with 422 on PATCH', async () => {
    const tenantId = await firstTenantId();
    const created = (await (
      await post(`${base}/tenant/${tenantId}/applications`, { name: 'App' })
    ).json()) as { id: string };

    const res = await fetch(
      `${base}/tenant/${tenantId}/applications/${created.id}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: '' }),
      },
    );

    expect(res.status).toBe(422);
  });

  it('returns 404 for an unknown tenant', async () => {
    const res = await fetch(
      `${base}/tenant/${crypto.randomUUID()}/applications`,
    );

    expect(res.status).toBe(404);
  });
});

describe('device handlers', () => {
  it('creates a device and lowercases the euis', async () => {
    const appId = await firstAppId();
    const res = await post(
      `${base}/devices`,
      validDevice(appId, 'AABBCCDDEEFF0001'),
    );
    const body = (await res.json()) as { dev_eui: string; id: string };

    expect(res.status).toBe(201);
    expect(body.id).toMatch(UUID_RE);
    expect(body.dev_eui).toBe('aabbccddeeff0001');
  });

  it('rejects an invalid DevEUI with 422', async () => {
    const appId = await firstAppId();
    const res = await post(
      `${base}/devices`,
      validDevice(appId, 'abc'),
    );

    expect(res.status).toBe(422);
  });

  it('returns 409 on a duplicate DevEUI', async () => {
    const appId = await firstAppId();
    const payload = validDevice(appId, 'aabbccddeeff0002');
    await post(`${base}/devices`, payload);

    const res = await post(`${base}/devices`, payload);

    expect(res.status).toBe(409);
  });

  it('lists devices filtered by app_id', async () => {
    const appId = await firstAppId();
    await post(`${base}/devices`, validDevice(appId, 'aabbccddeeff0003'));

    const res = await fetch(`${base}/devices?app_id=${appId}`);
    const devices = (await res.json()) as { dev_eui: string }[];

    expect(res.status).toBe(200);
    expect(
      devices.some((device) => device.dev_eui === 'aabbccddeeff0003'),
    ).toBe(true);
  });
});

describe('telemetry handlers', () => {
  it('returns a paginated history envelope for a dev_eui', async () => {
    const res = await fetch(`${base}/telemetry?dev_eui=aabbccddeeff0004&limit=5`);
    const body = (await res.json()) as {
      items: { time: string; dev_eui: string; payload: Record<string, unknown> }[];
      next_cursor: string | null;
    };

    expect(res.status).toBe(200);
    expect(body.items).toHaveLength(5);
    expect(body.items[0].dev_eui).toBe('aabbccddeeff0004');
    expect(typeof body.items[0].payload.temperature).toBe('number');
    expect(body.next_cursor).toContain('aabbccddeeff0004');
  });

  it('rejects a missing dev_eui with 422', async () => {
    const res = await fetch(`${base}/telemetry`);

    expect(res.status).toBe(422);
  });
});
