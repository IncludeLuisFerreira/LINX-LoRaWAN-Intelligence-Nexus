import { describe, expect, it } from 'vitest';
import { decodeToken, getPermissions, isTokenExpired } from './jwt';

function tokenWithPayload(payload: Record<string, unknown>): string {
  return `header.${btoa(JSON.stringify(payload))}.signature`;
}

describe('jwt utils', () => {
  it('decodifica o payload do token', () => {
    const token = tokenWithPayload({ sub: 'user-1', exp: 123 });

    expect(decodeToken(token)).toMatchObject({ sub: 'user-1', exp: 123 });
  });

  it('retorna null para token inválido', () => {
    expect(decodeToken('not-a-jwt')).toBeNull();
  });

  it('considera token expirado quando exp está no passado', () => {
    const now = 1_700_000_000_000;
    const token = tokenWithPayload({ exp: now / 1000 - 1 });

    expect(isTokenExpired(token, now)).toBe(true);
  });

  it('considera token válido quando exp está no futuro', () => {
    const now = 1_700_000_000_000;
    const token = tokenWithPayload({ exp: now / 1000 + 60 });

    expect(isTokenExpired(token, now)).toBe(false);
  });

  it('trata token sem exp como expirado', () => {
    expect(isTokenExpired(tokenWithPayload({ sub: 'user-1' }))).toBe(true);
  });
});

describe('getPermissions', () => {
  it('extrai as permissões da claim permissions', () => {
    const token = tokenWithPayload({
      permissions: ['device:create', 'device:read'],
    });

    expect(getPermissions(token)).toEqual(['device:create', 'device:read']);
  });

  it('ignora valores que não são strings', () => {
    const token = tokenWithPayload({
      permissions: ['device:create', 42, null, 'device:delete'],
    });

    expect(getPermissions(token)).toEqual(['device:create', 'device:delete']);
  });

  it('retorna lista vazia quando a claim não existe ou o token é inválido', () => {
    expect(getPermissions(tokenWithPayload({ sub: 'user-1' }))).toEqual([]);
    expect(getPermissions('not-a-jwt')).toEqual([]);
  });
});
