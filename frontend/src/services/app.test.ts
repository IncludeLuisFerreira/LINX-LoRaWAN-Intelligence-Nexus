import { describe, expect, it } from 'vitest';
import { loadApplicationsByTenant } from './app';
import type { TenantOutput } from './tenant';

const tenant = (id: string, name = id): TenantOutput => ({
  id,
  name,
  description: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
});

describe('loadApplicationsByTenant', () => {
  it('maps applications by tenant id', async () => {
    const tenants = [tenant('a'), tenant('b')];

    const result = await loadApplicationsByTenant(tenants, async (id) =>
      id === 'a' ? [{ id: '1', name: 'App A' } as never] : [],
    );

    expect(result).toEqual({ a: [{ id: '1', name: 'App A' }], b: [] });
  });

  it('keeps the tenants that succeeded when one request fails', async () => {
    const tenants = [tenant('a'), tenant('b'), tenant('c')];

    const result = await loadApplicationsByTenant(tenants, async (id) => {
      if (id === 'b') throw new Error('tenant b offline');
      return [{ id, name: `App ${id}` } as never];
    });

    expect(result).toEqual({
      a: [{ id: 'a', name: 'App a' }],
      c: [{ id: 'c', name: 'App c' }],
    });
    expect(result.b).toBeUndefined();
  });

  it('treats a non-array response as an empty list', async () => {
    const result = await loadApplicationsByTenant([tenant('a')], async () =>
      null as never,
    );

    expect(result).toEqual({ a: [] });
  });
});
