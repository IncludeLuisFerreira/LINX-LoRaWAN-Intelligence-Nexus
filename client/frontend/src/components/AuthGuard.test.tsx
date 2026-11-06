// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthGuard } from './AuthGuard';

const auth = vi.hoisted(() => ({
  accessToken: null as string | null,
  logout: vi.fn(),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: auth.accessToken, logout: auth.logout }),
}));

function tokenWithExp(exp: number): string {
  const payload = btoa(JSON.stringify({ exp }));
  return `header.${payload}.signature`;
}

function renderGuardedRoute() {
  return render(
    <MemoryRouter initialEntries={['/private']}>
      <Routes>
        <Route path="/login" element={<div>Página de login</div>} />
        <Route
          path="/private"
          element={
            <AuthGuard>
              <div>Conteúdo protegido</div>
            </AuthGuard>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AuthGuard', () => {
  beforeEach(() => {
    auth.accessToken = null;
    auth.logout.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('redireciona para /login quando não há token', () => {
    renderGuardedRoute();

    expect(screen.getByText('Página de login')).toBeTruthy();
    expect(screen.queryByText('Conteúdo protegido')).toBeNull();
  });

  it('redireciona para /login e faz logout quando o token expirou', () => {
    auth.accessToken = tokenWithExp(Math.floor(Date.now() / 1000) - 60);

    renderGuardedRoute();

    expect(screen.getByText('Página de login')).toBeTruthy();
    expect(screen.queryByText('Conteúdo protegido')).toBeNull();
    expect(auth.logout).toHaveBeenCalledTimes(1);
  });

  it('renderiza a rota protegida quando o token é válido', () => {
    auth.accessToken = tokenWithExp(Math.floor(Date.now() / 1000) + 3600);

    renderGuardedRoute();

    expect(screen.getByText('Conteúdo protegido')).toBeTruthy();
    expect(screen.queryByText('Página de login')).toBeNull();
    expect(auth.logout).not.toHaveBeenCalled();
  });
});
