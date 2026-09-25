import { describe, expect, it } from 'vitest';
import { allowedOrigins, resolveRequestOrigin } from './origin';

function request(url: string, headers: Record<string, string> = {}): Request {
  return new Request(url, { headers });
}

describe('allowedOrigins', () => {
  it('inclui o origin do SITE_URL', () => {
    expect(allowedOrigins().has('http://localhost:4321')).toBe(true);
  });

  it('inclui os VERCEL_* do ambiente', () => {
    process.env.VERCEL_URL = 'preview-abc.vercel.app';
    process.env.VERCEL_BRANCH_URL = 'branch-def.vercel.app';
    process.env.VERCEL_PROJECT_PRODUCTION_URL = 'app.example.com';

    const origins = allowedOrigins();

    expect(origins.has('https://preview-abc.vercel.app')).toBe(true);
    expect(origins.has('https://branch-def.vercel.app')).toBe(true);
    expect(origins.has('https://app.example.com')).toBe(true);

    delete process.env.VERCEL_URL;
    delete process.env.VERCEL_BRANCH_URL;
    delete process.env.VERCEL_PROJECT_PRODUCTION_URL;
  });
});

describe('resolveRequestOrigin', () => {
  it('usa o host da requisição quando está na allowlist', () => {
    process.env.VERCEL_URL = 'preview-abc.vercel.app';

    const url = new URL('https://preview-abc.vercel.app/api/auth/login');
    const origin = resolveRequestOrigin(
      request(url.toString(), {
        'x-forwarded-host': 'preview-abc.vercel.app',
        'x-forwarded-proto': 'https',
      }),
      url,
    );

    expect(origin).toBe('https://preview-abc.vercel.app');

    delete process.env.VERCEL_URL;
  });

  it('cai no SITE_URL quando o host não está autorizado', () => {
    const url = new URL('https://evil.example/api/auth/login');
    const origin = resolveRequestOrigin(
      request(url.toString(), {
        'x-forwarded-host': 'evil.example',
        'x-forwarded-proto': 'https',
      }),
      url,
    );

    expect(origin).toBe('http://localhost:4321');
  });

  it('ignora valores múltiplos em x-forwarded-host', () => {
    process.env.VERCEL_URL = 'preview-abc.vercel.app';

    const url = new URL('https://preview-abc.vercel.app/api/auth/login');
    const origin = resolveRequestOrigin(
      request(url.toString(), {
        'x-forwarded-host': 'preview-abc.vercel.app, internal.local',
        'x-forwarded-proto': 'https, http',
      }),
      url,
    );

    expect(origin).toBe('https://preview-abc.vercel.app');

    delete process.env.VERCEL_URL;
  });
});
