// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';
import { clearAccessToken, getAccessToken } from '../services/api';

const authService = vi.hoisted(() => ({ login: vi.fn() }));

vi.mock('../services/auth', () => ({ login: authService.login }));

function wrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

function makeAccessToken(): string {
  const encode = (value: object) =>
    btoa(JSON.stringify(value))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');

  return [
    encode({ alg: 'none', typ: 'JWT' }),
    encode({
      sub: 'user-1',
      email: 'user@example.com',
      permissions: ['user:read'],
      exp: Math.floor(Date.now() / 1000) + 3600,
    }),
    'signature',
  ].join('.');
}

describe('AuthContext', () => {
  beforeEach(() => {
    authService.login.mockReset();
    clearAccessToken();
  });

  afterEach(() => {
    cleanup();
    clearAccessToken();
  });

  it('popula accessToken e isAuthenticated após o login', async () => {
    const token = makeAccessToken();
    authService.login.mockResolvedValue({ access_token: token });
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.accessToken).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);

    await act(async () => {
      await result.current.login('user@example.com', 'secret');
    });

    expect(authService.login).toHaveBeenCalledWith(
      'user@example.com',
      'secret',
    );
    expect(result.current.accessToken).toBe(token);
    expect(result.current.isAuthenticated).toBe(true);
    expect(getAccessToken()).toBe(token);
  });

  it('expõe userId e email a partir das claims do JWT', async () => {
    authService.login.mockResolvedValue({ access_token: makeAccessToken() });
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.userId).toBeNull();
    expect(result.current.email).toBeNull();

    await act(async () => {
      await result.current.login('user@example.com', 'secret');
    });

    expect(result.current.userId).toBe('user-1');
    expect(result.current.email).toBe('user@example.com');
    expect(result.current.permissions).toEqual(['user:read']);
  });

  it('mantém accessToken nulo quando o login falha', async () => {
    authService.login.mockRejectedValue(new Error('Invalid credentials'));
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await expect(
        result.current.login('user@example.com', 'wrong'),
      ).rejects.toThrow('Invalid credentials');
    });

    expect(result.current.accessToken).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.userId).toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('logout limpa o estado e o token em memória', async () => {
    authService.login.mockResolvedValue({ access_token: makeAccessToken() });
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login('user@example.com', 'secret');
    });

    act(() => {
      result.current.logout();
    });

    expect(result.current.accessToken).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.userId).toBeNull();
    expect(getAccessToken()).toBeNull();
  });
});
