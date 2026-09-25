import { EncryptJWT, jwtDecrypt } from 'jose';
import type { AstroCookies } from 'astro';
import { SESSION_SECRET } from 'astro:env/server';
import type { Auth0User } from './auth0';

const COOKIE_NAME = 'linx_session';
const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7;

let keyPromise: Promise<Uint8Array> | null = null;

function getKey(): Promise<Uint8Array> {
  if (!keyPromise) {
    keyPromise = crypto.subtle
      .digest('SHA-256', new TextEncoder().encode(SESSION_SECRET))
      .then((buf) => new Uint8Array(buf));
  }
  return keyPromise;
}

async function encrypt(user: Auth0User): Promise<string> {
  const key = await getKey();
  return new EncryptJWT({ user })
    .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_TTL_SECONDS}s`)
    .encrypt(key);
}

async function decrypt(token: string): Promise<Auth0User | null> {
  try {
    const key = await getKey();
    const { payload } = await jwtDecrypt(token, key);
    const user = payload.user as Auth0User | undefined;
    return user?.sub ? user : null;
  } catch {
    return null;
  }
}

export function cookieOptions() {
  return {
    httpOnly: true,
    secure: import.meta.env.PROD,
    sameSite: 'lax' as const,
    path: '/',
    maxAge: SESSION_TTL_SECONDS,
  };
}

export async function setSession(
  cookies: AstroCookies,
  user: Auth0User,
): Promise<void> {
  cookies.set(COOKIE_NAME, await encrypt(user), cookieOptions());
}

export async function getSession(
  cookies: AstroCookies,
): Promise<Auth0User | null> {
  const token = cookies.get(COOKIE_NAME)?.value;
  return token ? decrypt(token) : null;
}

export function clearSession(cookies: AstroCookies): void {
  cookies.delete(COOKIE_NAME, { path: '/' });
}
