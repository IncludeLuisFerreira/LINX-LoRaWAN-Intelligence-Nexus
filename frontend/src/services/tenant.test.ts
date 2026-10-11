import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { tenantService } from './tenant';

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mocked = vi.mocked(api);

describe('tenantService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('creates a tenant with POST /tenant/', async () => {
    mocked.post.mockResolvedValue({ data: { id: 't1' } });

    const result = await tenantService.create({ name: 'ACME' });

    expect(mocked.post).toHaveBeenCalledWith('/tenant/', { name: 'ACME' });
    expect(result).toEqual({ id: 't1' });
  });

  it('lists tenants with GET /tenant', async () => {
    mocked.get.mockResolvedValue({ data: [{ id: 't1' }] });

    const result = await tenantService.list();

    expect(mocked.get).toHaveBeenCalledWith('/tenant', { params: undefined });
    expect(result).toEqual([{ id: 't1' }]);
  });

  it('gets a tenant by id', async () => {
    mocked.get.mockResolvedValue({ data: { id: 't1' } });

    await tenantService.get('t1');

    expect(mocked.get).toHaveBeenCalledWith('/tenant/t1');
  });

  it('updates a tenant with PATCH /tenant/{id}', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 't1' } });

    await tenantService.update('t1', { name: 'Novo' });

    expect(mocked.patch).toHaveBeenCalledWith('/tenant/t1', { name: 'Novo' });
  });

  it('removes a tenant with DELETE /tenant/{id}', async () => {
    mocked.delete.mockResolvedValue({ data: null });

    await tenantService.remove('t1');

    expect(mocked.delete).toHaveBeenCalledWith('/tenant/t1');
  });
});
