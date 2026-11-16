import { jwtDecode } from 'jwt-decode';

export interface JwtPayload {
  exp?: number;
  permissions?: unknown;
  [key: string]: unknown;
}

/**
 * Decodifica o payload de um JWT sem validar a assinatura.
 * Retorna `null` quando o token é inválido ou malformado.
 */
export function decodeToken(token: string): JwtPayload | null {
  try {
    return jwtDecode<JwtPayload>(token);
  } catch {
    return null;
  }
}

/**
 * Verifica se o token expirou com base no campo `exp` (segundos).
 * Tokens inválidos ou sem `exp` são tratados como expirados.
 */
export function isTokenExpired(
  token: string,
  now: number = Date.now(),
): boolean {
  const payload = decodeToken(token);

  if (!payload || typeof payload.exp !== 'number') {
    return true;
  }

  return payload.exp * 1000 <= now;
}

/**
 * Extrai as permissões da claim `permissions` do JWT.
 * Valores inválidos ou ausentes resultam em uma lista vazia.
 */
export function getPermissions(token: string): string[] {
  const payload = decodeToken(token);

  if (!payload || !Array.isArray(payload.permissions)) {
    return [];
  }

  return payload.permissions.filter(
    (permission): permission is string => typeof permission === 'string',
  );
}
