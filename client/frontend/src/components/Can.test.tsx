// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Can } from './Can';

const auth = vi.hoisted(() => ({
  permissions: [] as string[],
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ permissions: auth.permissions }),
}));

describe('Can', () => {
  beforeEach(() => {
    auth.permissions = [];
  });

  afterEach(() => {
    cleanup();
  });

  it('renderiza o conteúdo quando o usuário possui a permissão', () => {
    auth.permissions = ['device:create', 'device:read'];

    render(
      <Can permission="device:create">
        <button type="button">Novo dispositivo</button>
      </Can>,
    );

    expect(screen.getByText('Novo dispositivo')).toBeTruthy();
  });

  it('não renderiza o conteúdo quando falta a permissão', () => {
    auth.permissions = ['device:read'];

    render(
      <Can permission="device:create">
        <button type="button">Novo dispositivo</button>
      </Can>,
    );

    expect(screen.queryByText('Novo dispositivo')).toBeNull();
  });

  it('não renderiza quando o usuário não possui permissão alguma', () => {
    render(
      <Can permission="device:create">
        <button type="button">Novo dispositivo</button>
      </Can>,
    );

    expect(screen.queryByText('Novo dispositivo')).toBeNull();
  });
});
