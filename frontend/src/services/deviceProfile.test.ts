import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import { deviceProfileService } from './deviceProfile';

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

describe('deviceProfileService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists device profiles of an application with GET ?app_id=', async () => {
    mocked.get.mockResolvedValue({ data: [] });

    await deviceProfileService.listByApp('app-1');

    expect(mocked.get).toHaveBeenCalledWith('/device-profile/', {
      params: { app_id: 'app-1' },
    });
  });
});
