import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import { deviceService } from './device';

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

describe('deviceService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists devices of an application with GET ?app_id=', async () => {
    mocked.get.mockResolvedValue({ data: [] });

    await deviceService.listByApp('app-1');

    expect(mocked.get).toHaveBeenCalledWith('/devices', {
      params: { app_id: 'app-1' },
    });
  });

  it('creates a device with POST /devices', async () => {
    mocked.post.mockResolvedValue({ data: { id: 'd1' } });
    const payload = {
      dev_eui: 'aabbccddeeff0011',
      app_id: 'app-1',
      join_eui: '1122334455667788',
      app_key: '00112233445566778899aabbccddeeff',
      device_profile_id: 'profile-1',
    };

    await deviceService.create(payload);

    expect(mocked.post).toHaveBeenCalledWith('/devices', payload);
  });

  it('removes a device with DELETE /devices/{id}', async () => {
    mocked.delete.mockResolvedValue({ data: null });

    await deviceService.remove('d1');

    expect(mocked.delete).toHaveBeenCalledWith('/devices/d1');
  });

  it('updates a device nickname with PATCH /devices/{id}', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 'd1', nickname: 'Bomba 1' } });

    await deviceService.update('d1', { nickname: 'Bomba 1' });

    expect(mocked.patch).toHaveBeenCalledWith('/devices/d1', {
      nickname: 'Bomba 1',
    });
  });
});
