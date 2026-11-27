// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';
import { clearAccessToken, getAccessToken } from '../services/api';

const authService = vi.hoisted(() => ({ login: vi.fn() }));

vi.mock('../services/auth', () => ({ login: authService.login }));

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
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
    authService.login.mockResolvedValue({ access_token: 'jwt-access' });
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
    expect(result.current.accessToken).toBe('jwt-access');
    expect(result.current.isAuthenticated).toBe(true);
    expect(getAccessToken()).toBe('jwt-access');
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
    expect(getAccessToken()).toBeNull();
  });

  it('logout limpa o estado e o token em memória', async () => {
    authService.login.mockResolvedValue({ access_token: 'jwt-access' });
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login('user@example.com', 'secret');
    });

    act(() => {
      result.current.logout();
    });

    expect(result.current.accessToken).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(getAccessToken()).toBeNull();
  });
});
