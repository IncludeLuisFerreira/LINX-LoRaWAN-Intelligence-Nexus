import { beforeAll, describe, expect, it, vi } from 'vitest';
import {
  SignJWT,
  exportJWK,
  generateKeyPair,
  type CryptoKey,
  type JWK,
} from 'jose';
import {
  buildAuthorizeUrl,
  buildLogoutUrl,
  callbackUrl,
  exchangeCode,
  verifyIdToken,
} from './auth0';

const DOMAIN = 'tenant.example.auth0.com';
const ISSUER = `https://${DOMAIN}/`;
const CLIENT_ID = 'test-client-id';

const discovery = {
  issuer: ISSUER,
  authorization_endpoint: `${ISSUER}authorize`,
  token_endpoint: `${ISSUER}oauth/token`,
  jwks_uri: `${ISSUER}.well-known/jwks.json`,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let publicJwk: JWK;
let privateKey: CryptoKey;
let otherPrivateKey: CryptoKey;
let tokenResponder: () => Response;

beforeAll(async () => {
  const key = await generateKeyPair('RS256', { extractable: true });
  privateKey = key.privateKey;
  const jwk = await exportJWK(key.publicKey);
  publicJwk = { ...jwk, kid: 'test-key', alg: 'RS256', use: 'sig' };

  const other = await generateKeyPair('RS256', { extractable: true });
  otherPrivateKey = other.privateKey;

  tokenResponder = () => json({ id_token: 'id', access_token: 'access' });

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.endsWith('/.well-known/openid-configuration')) {
        return json(discovery);
      }
      if (url.endsWith('/.well-known/jwks.json')) {
        return json({ keys: [publicJwk] });
      }
      if (url.endsWith('/oauth/token')) {
        return tokenResponder();
      }
      return new Response('not found', { status: 404 });
    }),
  );
});

async function signIdToken(options: {
  nonce: string;
  key?: CryptoKey;
  subject?: string;
}): Promise<string> {
  return new SignJWT({ nonce: options.nonce })
    .setProtectedHeader({ alg: 'RS256', kid: 'test-key' })
    .setIssuer(ISSUER)
    .setAudience(CLIENT_ID)
    .setSubject(options.subject ?? 'auth0|123')
    .setIssuedAt()
    .setExpirationTime('5m')
    .sign(options.key ?? privateKey);
}

describe('callbackUrl', () => {
  it('aponta para /api/auth/callback no SITE_URL por padrão', () => {
    expect(callbackUrl()).toBe('http://localhost:4321/api/auth/callback');
  });

  it('usa a origem informada', () => {
    expect(callbackUrl('https://preview.vercel.app')).toBe(
      'https://preview.vercel.app/api/auth/callback',
    );
  });
});

describe('buildAuthorizeUrl', () => {
  it('inclui os parâmetros obrigatórios e PKCE S256', async () => {
    const redirectUri = 'https://preview.vercel.app/api/auth/callback';
    const url = new URL(
      await buildAuthorizeUrl({
        state: 'estado',
        nonce: 'nonce',
        codeChallenge: 'desafio',
        redirectUri,
      }),
    );

    expect(url.origin).toBe(`https://${DOMAIN}`);
    expect(url.pathname).toBe('/authorize');
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('client_id')).toBe(CLIENT_ID);
    expect(url.searchParams.get('redirect_uri')).toBe(redirectUri);
    expect(url.searchParams.get('scope')).toBe('openid profile email');
    expect(url.searchParams.get('state')).toBe('estado');
    expect(url.searchParams.get('nonce')).toBe('nonce');
    expect(url.searchParams.get('code_challenge')).toBe('desafio');
    expect(url.searchParams.get('code_challenge_method')).toBe('S256');
    expect(url.searchParams.get('audience')).toBeNull();
  });

  it('inclui screen_hint e login_hint quando informados', async () => {
    const url = new URL(
      await buildAuthorizeUrl({
        state: 's',
        nonce: 'n',
        codeChallenge: 'c',
        redirectUri: callbackUrl(),
        screenHint: 'signup',
        loginHint: 'user@example.com',
      }),
    );

    expect(url.searchParams.get('screen_hint')).toBe('signup');
    expect(url.searchParams.get('login_hint')).toBe('user@example.com');
  });
});

describe('exchangeCode', () => {
  it('retorna os tokens em caso de sucesso', async () => {
    tokenResponder = () =>
      json({ id_token: 'id-token', access_token: 'access-token' });

    await expect(
      exchangeCode('code', 'verifier', callbackUrl()),
    ).resolves.toEqual({
      id_token: 'id-token',
      access_token: 'access-token',
    });
  });

  it('lança quando o token_endpoint responde erro', async () => {
    tokenResponder = () => new Response('invalid_grant', { status: 400 });

    await expect(
      exchangeCode('code', 'verifier', callbackUrl()),
    ).rejects.toThrow(/Troca de code falhou/);
  });
});

describe('verifyIdToken', () => {
  it('valida um id_token legítimo e extrai o usuário', async () => {
    const token = await signIdToken({ nonce: 'nonce-ok' });

    const user = await verifyIdToken(token, 'nonce-ok');

    expect(user.sub).toBe('auth0|123');
  });

  it('rejeita nonce divergente', async () => {
    const token = await signIdToken({ nonce: 'nonce-ok' });

    await expect(verifyIdToken(token, 'nonce-errado')).rejects.toThrow(
      /nonce inválido/,
    );
  });

  it('rejeita assinatura inválida', async () => {
    const token = await signIdToken({
      nonce: 'nonce-ok',
      key: otherPrivateKey,
    });

    await expect(verifyIdToken(token, 'nonce-ok')).rejects.toThrow();
  });
});

describe('buildLogoutUrl', () => {
  it('aponta para o v2/logout com returnTo', () => {
    const url = new URL(buildLogoutUrl('http://localhost:4321'));

    expect(url.origin).toBe(`https://${DOMAIN}`);
    expect(url.pathname).toBe('/v2/logout');
    expect(url.searchParams.get('client_id')).toBe(CLIENT_ID);
    expect(url.searchParams.get('returnTo')).toBe('http://localhost:4321');
  });
});
