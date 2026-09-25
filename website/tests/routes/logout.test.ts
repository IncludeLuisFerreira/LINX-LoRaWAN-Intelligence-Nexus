import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCookies, createRedirect } from '../../src/test/context';

const logoutUrl = 'https://tenant.example.auth0.com/v2/logout?client_id=x';

vi.mock('../../src/lib/session', () => ({
  clearSession: vi.fn(),
}));

vi.mock('../../src/lib/auth0', () => ({
  buildLogoutUrl: vi.fn(() => logoutUrl),
}));

import { clearSession } from '../../src/lib/session';
import { POST } from '../../src/pages/api/auth/logout';

describe('POST /api/auth/logout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('limpa a sessão e redireciona para o logout do Auth0', async () => {
    const { cookies } = createCookies();

    const res = await POST({
      cookies,
      redirect: createRedirect(),
    } as never);

    expect(clearSession).toHaveBeenCalledWith(cookies);
    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe(logoutUrl);
  });
});
