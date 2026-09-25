import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCookies, createRedirect } from '../../src/test/context';

vi.mock('../../src/lib/auth0', () => ({
  exchangeCode: vi.fn(),
  verifyIdToken: vi.fn(),
  callbackUrl: (origin: string) => `${origin}/api/auth/callback`,
}));

vi.mock('../../src/lib/session', () => ({
  setSession: vi.fn(async () => undefined),
}));

import { exchangeCode, verifyIdToken } from '../../src/lib/auth0';
import { setSession } from '../../src/lib/session';
import { GET } from '../../src/pages/api/auth/callback';

const CALLBACK = 'http://localhost:4321/api/auth/callback';
const USER = { sub: 'auth0|123', email: 'ada@example.com' };

function context(
  query: Record<string, string>,
  cookies: ReturnType<typeof createCookies>,
) {
  const url = new URL(CALLBACK);
  for (const [key, value] of Object.entries(query)) {
    url.searchParams.set(key, value);
  }
  return {
    request: new Request(url),
    url,
    cookies: cookies.cookies,
    redirect: createRedirect(),
  } as never;
}

function validCookies() {
  return createCookies({
    linx_oauth_state: 'estado',
    linx_oauth_nonce: 'nonce',
    linx_oauth_verifier: 'verifier',
  });
}

describe('GET /api/auth/callback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(exchangeCode).mockResolvedValue({ id_token: 'id-token' });
    vi.mocked(verifyIdToken).mockResolvedValue(USER);
  });

  it('conclui o login e redireciona para o caminho pós-login', async () => {
    const cookies = validCookies();

    const res = await GET(
      context({ code: 'code', state: 'estado' }, cookies),
    );

    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe('/');
    expect(setSession).toHaveBeenCalledWith(cookies.cookies, USER);
  });

  it('remove os cookies transitórios', async () => {
    const cookies = validCookies();

    await GET(context({ code: 'code', state: 'estado' }, cookies));

    expect(cookies.store.has('linx_oauth_state')).toBe(false);
    expect(cookies.store.has('linx_oauth_nonce')).toBe(false);
    expect(cookies.store.has('linx_oauth_verifier')).toBe(false);
  });

  it('rejeita state divergente sem trocar o code', async () => {
    const cookies = validCookies();

    const res = await GET(
      context({ code: 'code', state: 'divergente' }, cookies),
    );

    expect(res.status).toBe(400);
    expect(exchangeCode).not.toHaveBeenCalled();
  });

  it('rejeita callback sem code', async () => {
    const cookies = validCookies();

    const res = await GET(context({ state: 'estado' }, cookies));

    expect(res.status).toBe(400);
    expect(exchangeCode).not.toHaveBeenCalled();
  });

  it('responde erro genérico quando o Auth0 retorna erro', async () => {
    const cookies = validCookies();

    const res = await GET(
      context({ error: 'access_denied' }, cookies),
    );

    expect(res.status).toBe(400);
    await expect(res.text()).resolves.toBe(
      'Não foi possível concluir o login.',
    );
    expect(exchangeCode).not.toHaveBeenCalled();
  });

  it('responde 401 quando a troca de code falha', async () => {
    vi.mocked(exchangeCode).mockRejectedValue(new Error('invalid_grant'));
    const cookies = validCookies();

    const res = await GET(
      context({ code: 'code', state: 'estado' }, cookies),
    );

    expect(res.status).toBe(401);
    expect(setSession).not.toHaveBeenCalled();
  });

  it('responde 401 quando o id_token está ausente', async () => {
    vi.mocked(exchangeCode).mockResolvedValue({});
    const cookies = validCookies();

    const res = await GET(
      context({ code: 'code', state: 'estado' }, cookies),
    );

    expect(res.status).toBe(401);
    expect(setSession).not.toHaveBeenCalled();
  });
});
