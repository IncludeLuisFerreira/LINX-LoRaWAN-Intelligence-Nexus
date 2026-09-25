import { ALLOWED_ORIGINS, SITE_URL } from 'astro:env/server';

function originFrom(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    return new URL(withScheme).origin;
  } catch {
    return null;
  }
}

function firstValue(header: string | null): string | undefined {
  return header?.split(',')[0]?.trim() || undefined;
}

export function allowedOrigins(): Set<string> {
  const candidates = [
    SITE_URL,
    ...(ALLOWED_ORIGINS ? ALLOWED_ORIGINS.split(',') : []),
    process.env.VERCEL_URL,
    process.env.VERCEL_BRANCH_URL,
    process.env.VERCEL_PROJECT_PRODUCTION_URL,
  ];

  const origins = new Set<string>();
  for (const candidate of candidates) {
    const origin = originFrom(candidate);
    if (origin) origins.add(origin);
  }
  return origins;
}

/**
 * Resolve a origem pública da requisição para montar o redirect_uri do OAuth.
 * Só aceita hosts presentes na allowlist (SITE_URL, ALLOWED_ORIGINS e os
 * VERCEL_* injetados pela plataforma), evitando host header injection.
 */
export function resolveRequestOrigin(request: Request, url: URL): string {
  const allowed = allowedOrigins();
  const host = firstValue(request.headers.get('x-forwarded-host')) ??
    firstValue(request.headers.get('host'));
  const proto =
    firstValue(request.headers.get('x-forwarded-proto')) ??
    url.protocol.replace(/:$/, '');

  const candidate = host ? originFrom(`${proto}://${host}`) : null;
  if (candidate && allowed.has(candidate)) return candidate;

  return originFrom(SITE_URL) ?? url.origin;
}
