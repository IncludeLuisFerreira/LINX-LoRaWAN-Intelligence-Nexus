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
