import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createCookies, createRedirect } from '../../src/test/context';

const authorizeUrl = 'https://tenant.example.auth0.com/authorize?x=1';

vi.mock('../../src/lib/auth0', () => ({
  buildAuthorizeUrl: vi.fn(async () => authorizeUrl),
}));

import { buildAuthorizeUrl } from '../../src/lib/auth0';
import { GET } from '../../src/pages/api/auth/login';

describe('GET /api/auth/login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('grava os cookies transitórios e redireciona para o Auth0', async () => {
    const { cookies, store } = createCookies();
    const url = new URL(
      'http://localhost:4321/api/auth/login?screen_hint=signup',
    );

    const res = await GET({
      url,
      cookies,
      redirect: createRedirect(),
    } as never);

    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe(authorizeUrl);
    expect(store.has('linx_oauth_state')).toBe(true);
    expect(store.has('linx_oauth_nonce')).toBe(true);
    expect(store.has('linx_oauth_verifier')).toBe(true);

    const call = vi.mocked(buildAuthorizeUrl).mock.calls[0][0];
    expect(call.state).toBe(store.get('linx_oauth_state'));
    expect(call.nonce).toBe(store.get('linx_oauth_nonce'));
    expect(call.codeChallenge).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(call.screenHint).toBe('signup');
  });

  it('gera state/nonce/verifier aleatórios a cada requisição', async () => {
    const first = createCookies();
    const second = createCookies();

    await GET({
      url: new URL('http://localhost:4321/api/auth/login'),
      cookies: first.cookies,
      redirect: createRedirect(),
    } as never);
    await GET({
      url: new URL('http://localhost:4321/api/auth/login'),
      cookies: second.cookies,
      redirect: createRedirect(),
    } as never);

    expect(first.store.get('linx_oauth_state')).not.toBe(
      second.store.get('linx_oauth_state'),
    );
    expect(first.store.get('linx_oauth_verifier')).not.toBe(
      second.store.get('linx_oauth_verifier'),
    );
  });
});
