import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import { applicationService, loadApplicationsByTenant } from './app';
import type { TenantOutput } from './tenant';

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mocked = api as unknown as Record<
  'get' | 'post' | 'patch' | 'delete',
  Mock
>;

const tenant = (id: string, name = id): TenantOutput => ({
  id,
  name,
  description: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
});

describe('applicationService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('creates an application under a tenant with POST', async () => {
    mocked.post.mockResolvedValue({ data: { id: 'a1' } });

    await applicationService.create('t1', { name: 'App' });

    expect(mocked.post).toHaveBeenCalledWith('/tenant/t1/applications', {
      name: 'App',
    });
  });

  it('lists applications of a tenant with GET', async () => {
    mocked.get.mockResolvedValue({ data: [] });

    await applicationService.listByTenant('t1');

    expect(mocked.get).toHaveBeenCalledWith('/tenant/t1/applications');
  });

  it('gets a single application', async () => {
    mocked.get.mockResolvedValue({ data: { id: 'a1' } });

    await applicationService.get('t1', 'a1');

    expect(mocked.get).toHaveBeenCalledWith('/tenant/t1/applications/a1');
  });

  it('updates an application with PATCH', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 'a1' } });

    await applicationService.update('t1', 'a1', { name: 'Novo' });

    expect(mocked.patch).toHaveBeenCalledWith('/tenant/t1/applications/a1', {
      name: 'Novo',
    });
  });

  it('removes an application with DELETE', async () => {
    mocked.delete.mockResolvedValue({ data: null });

    await applicationService.remove('t1', 'a1');

    expect(mocked.delete).toHaveBeenCalledWith('/tenant/t1/applications/a1');
  });
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
    const result = await loadApplicationsByTenant(
      [tenant('a')],
      async () => null as never,
    );

    expect(result).toEqual({ a: [] });
  });
});
