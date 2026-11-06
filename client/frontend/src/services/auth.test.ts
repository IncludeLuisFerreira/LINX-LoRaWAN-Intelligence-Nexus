import { beforeEach, describe, expect, it, vi } from 'vitest';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock('./api', () => ({ api: { post } }));

import { login } from './auth';

describe('login', () => {
  beforeEach(() => {
    post.mockReset();
  });

  it('posts the credentials to /auth/login and returns the access token', async () => {
    post.mockResolvedValue({ data: { access_token: 'jwt-access' } });

    await expect(login('user@example.com', 'secret')).resolves.toEqual({
      access_token: 'jwt-access',
    });
    expect(post).toHaveBeenCalledWith('/auth/login', {
      email: 'user@example.com',
      password: 'secret',
    });
  });

  it('propagates backend errors', async () => {
    post.mockRejectedValue(new Error('Invalid credentials'));

    await expect(login('user@example.com', 'wrong')).rejects.toThrow(
      'Invalid credentials',
    );
  });
});
