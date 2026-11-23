import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from 'vitest';
import Users from './Users';
import { userService, type UserOutput } from '../../services/user';

vi.mock('../../services/user', async () => {
  const actual = await vi.importActual<typeof import('../../services/user')>(
    '../../services/user',
  );
  return {
    ...actual,
    userService: {
      list: vi.fn(),
      invite: vi.fn(),
      updateRole: vi.fn(),
      deactivate: vi.fn(),
    },
  };
});

const mocked = userService as unknown as Record<
  'list' | 'invite' | 'updateRole' | 'deactivate',
  Mock
>;

const users: UserOutput[] = [
  {
    id: 'u1',
    email: 'admin@example.com',
    is_admin: true,
    is_active: true,
    email_verified: true,
    note: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'u2',
    email: 'member@example.com',
    is_admin: false,
    is_active: true,
    email_verified: true,
    note: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

function renderUsers() {
  return render(
    <MemoryRouter initialEntries={['/tenants/org-1/users']}>
      <Routes>
        <Route path="/tenants/:tenantId/users" element={<Users />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Users', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocked.list.mockResolvedValue(users);
    mocked.invite.mockResolvedValue({ invite_token: 'token-123' });
    mocked.updateRole.mockResolvedValue({ ...users[1], is_admin: true });
    mocked.deactivate.mockResolvedValue({ ...users[1], is_active: false });
  });

  afterEach(() => cleanup());

  it('lista os usuários da organização com papel e status', async () => {
    renderUsers();

    expect(await screen.findByText('admin@example.com')).toBeTruthy();
    expect(screen.getByText('member@example.com')).toBeTruthy();
    expect(screen.getByText('Administrador')).toBeTruthy();
    expect(screen.getAllByText('Ativo')).toHaveLength(2);
    expect(mocked.list).toHaveBeenCalledOnce();
  });

  it('convida um usuário e exibe o link gerado', async () => {
    const user = userEvent.setup();
    renderUsers();
    await screen.findByText('admin@example.com');

    await user.click(screen.getByRole('button', { name: /convidar usuário/i }));
    await user.type(await screen.findByLabelText('E-mail'), 'new@example.com');
    await user.selectOptions(screen.getByLabelText('Papel'), 'admin');
    await user.click(screen.getByRole('button', { name: 'Gerar convite' }));

    await waitFor(() =>
      expect(mocked.invite).toHaveBeenCalledWith('org-1', {
        email: 'new@example.com',
        role: 'admin',
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      '/invite/token-123',
    );
  });

  it('altera o papel de um usuário', async () => {
    const user = userEvent.setup();
    renderUsers();
    await screen.findByText('member@example.com');

    await user.click(
      screen.getByRole('button', {
        name: 'Alterar papel de member@example.com',
      }),
    );
    await user.selectOptions(
      await screen.findByLabelText('Novo papel'),
      'admin',
    );
    await user.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() =>
      expect(mocked.updateRole).toHaveBeenCalledWith('u2', 'admin'),
    );
  });

  it('desativa um usuário após confirmação', async () => {
    const user = userEvent.setup();
    renderUsers();
    await screen.findByText('member@example.com');

    await user.click(
      screen.getByRole('button', { name: 'Desativar member@example.com' }),
    );
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Desativar' }));

    await waitFor(() => expect(mocked.deactivate).toHaveBeenCalledWith('u2'));
  });
});
