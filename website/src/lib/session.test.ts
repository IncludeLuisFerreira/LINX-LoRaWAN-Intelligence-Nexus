import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Auth0User } from './auth0';
import {
  SESSION_TTL_SECONDS,
  clearSession,
  cookieOptions,
  getSession,
  setSession,
} from './session';
import { createCookies } from '../test/context';

const USER: Auth0User = {
  sub: 'auth0|123',
  name: 'Ada Lovelace',
  email: 'ada@example.com',
};

const COOKIE_NAME = 'linx_session';

describe('session', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('faz round-trip de setSession/getSession', async () => {
    const { cookies } = createCookies();

    await setSession(cookies, USER);

    expect(await getSession(cookies)).toEqual(USER);
  });

  it('retorna null quando não há cookie', async () => {
    const { cookies } = createCookies();

    expect(await getSession(cookies)).toBeNull();
  });

  it('retorna null para token adulterado', async () => {
    const { cookies, store } = createCookies();
    await setSession(cookies, USER);

    const token = store.get(COOKIE_NAME)!;
    const tampered = `${token.slice(0, -1)}${token.endsWith('a') ? 'b' : 'a'}`;
    store.set(COOKIE_NAME, tampered);

    expect(await getSession(cookies)).toBeNull();
  });

  it('retorna null para token que não é JWE', async () => {
    const { cookies } = createCookies({ [COOKIE_NAME]: 'not-a-token' });

    expect(await getSession(cookies)).toBeNull();
  });

  it('retorna null quando a sessão expirou', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-01-01T00:00:00Z'));

    const { cookies } = createCookies();
    await setSession(cookies, USER);

    vi.setSystemTime(
      new Date(Date.now() + (SESSION_TTL_SECONDS + 60) * 1000),
    );

    expect(await getSession(cookies)).toBeNull();
  });

  it('remove o cookie de sessão', async () => {
    const { cookies, store } = createCookies();
    await setSession(cookies, USER);
    expect(store.has(COOKIE_NAME)).toBe(true);

    clearSession(cookies);

    expect(store.has(COOKIE_NAME)).toBe(false);
  });

  it('usa opções de cookie seguras', () => {
    const options = cookieOptions();

    expect(options.httpOnly).toBe(true);
    expect(options.sameSite).toBe('lax');
    expect(options.path).toBe('/');
    expect(options.maxAge).toBe(SESSION_TTL_SECONDS);
  });
});
