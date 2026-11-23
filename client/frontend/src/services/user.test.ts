import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import { inviteLink, userService } from './user';

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

const mocked = api as unknown as Record<'get' | 'post' | 'patch', Mock>;

describe('userService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lista usuários com GET /user', async () => {
    mocked.get.mockResolvedValue({ data: [{ id: 'u1' }] });

    const result = await userService.list();

    expect(mocked.get).toHaveBeenCalledWith('/user');
    expect(result).toEqual([{ id: 'u1' }]);
  });

  it('convida usuário com POST /orgs/{orgId}/invite', async () => {
    mocked.post.mockResolvedValue({ data: { invite_token: 'token-123' } });

    const result = await userService.invite('org-1', {
      email: 'user@example.com',
      role: 'admin',
    });

    expect(mocked.post).toHaveBeenCalledWith('/orgs/org-1/invite', {
      email: 'user@example.com',
      role: 'admin',
    });
    expect(result).toEqual({ invite_token: 'token-123' });
  });

  it('altera o papel com PATCH /user/{id}', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 'u1', is_admin: true } });

    const result = await userService.updateRole('u1', 'admin');

    expect(mocked.patch).toHaveBeenCalledWith('/user/u1', { role: 'admin' });
    expect(result).toEqual({ id: 'u1', is_admin: true });
  });

  it('desativa o usuário com PATCH /user/{id}', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 'u1', is_active: false } });

    await userService.deactivate('u1');

    expect(mocked.patch).toHaveBeenCalledWith('/user/u1', {
      is_active: false,
    });
  });
});

describe('inviteLink', () => {
  it('usa o link devolvido pelo backend', () => {
    expect(inviteLink({ invite_link: 'https://linx.local/i/abc' })).toBe(
      'https://linx.local/i/abc',
    );
  });

  it('monta o link a partir do token quando só o token é devolvido', () => {
    expect(inviteLink({ invite_token: 'abc' })).toBe(
      `${window.location.origin}/invite/abc`,
    );
  });

  it('retorna string vazia quando a resposta não traz link nem token', () => {
    expect(inviteLink({})).toBe('');
  });
});
