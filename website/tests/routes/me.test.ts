import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCookies } from '../../src/test/context';

vi.mock('../../src/lib/session', () => ({
  getSession: vi.fn(),
}));

import { getSession } from '../../src/lib/session';
import { GET } from '../../src/pages/api/auth/me';

const USER = { sub: 'auth0|123', email: 'ada@example.com' };

describe('GET /api/auth/me', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('responde 401 com user null quando não há sessão', async () => {
    vi.mocked(getSession).mockResolvedValue(null);
    const { cookies } = createCookies();

    const res = await GET({ cookies } as never);

    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ user: null });
  });

  it('responde 200 com o usuário e sem cache quando há sessão', async () => {
    vi.mocked(getSession).mockResolvedValue(USER);
    const { cookies } = createCookies();

    const res = await GET({ cookies } as never);

    expect(res.status).toBe(200);
    expect(res.headers.get('cache-control')).toBe('no-store');
    await expect(res.json()).resolves.toEqual({ user: USER });
  });
});
