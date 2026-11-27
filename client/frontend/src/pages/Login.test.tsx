// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Login from './Login';

const auth = vi.hoisted(() => ({ login: vi.fn() }));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ login: auth.login }),
}));

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/orgs" element={<div>Página de orgs</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Login page', () => {
  beforeEach(() => {
    auth.login.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('submete credenciais válidas e redireciona para /orgs', async () => {
    auth.login.mockResolvedValue({ access_token: 'jwt-access' });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('E-mail'), 'user@example.com');
    await user.type(screen.getByLabelText('Senha'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    await waitFor(() => {
      expect(auth.login).toHaveBeenCalledWith('user@example.com', 'secret');
    });
    expect(await screen.findByText('Página de orgs')).toBeTruthy();
  });

  it('exibe a mensagem de erro retornada pela API', async () => {
    auth.login.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 401'), {
        isAxiosError: true,
        response: { data: { detail: 'Credenciais inválidas' } },
      }),
    );
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('E-mail'), 'user@example.com');
    await user.type(screen.getByLabelText('Senha'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByText('Credenciais inválidas')).toBeTruthy();
    expect(screen.queryByText('Página de orgs')).toBeNull();
  });

  it('bloqueia submit com e-mail inválido pela validação Zod', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('E-mail'), 'invalido');
    await user.type(screen.getByLabelText('Senha'), 'secret');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByText('Formato de e-mail inválido')).toBeTruthy();
    expect(auth.login).not.toHaveBeenCalled();
  });
});
