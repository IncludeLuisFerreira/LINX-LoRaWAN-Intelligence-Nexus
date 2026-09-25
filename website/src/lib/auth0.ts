import { createRemoteJWKSet, jwtVerify, type JWTPayload } from 'jose';
import {
  AUTH0_AUDIENCE,
  AUTH0_CLIENT_ID,
  AUTH0_CLIENT_SECRET,
  AUTH0_DOMAIN,
  AUTH0_SCOPE,
  SITE_URL,
} from 'astro:env/server';

export interface Auth0User {
  sub: string;
  name?: string;
  nickname?: string;
  email?: string;
  picture?: string;
}

interface DiscoveryDocument {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  jwks_uri: string;
}

let discoveryPromise: Promise<DiscoveryDocument> | null = null;
let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function getIssuer(): string {
  return `https://${AUTH0_DOMAIN}/`;
}

export function callbackUrl(): string {
  return new URL('/api/auth/callback', SITE_URL).toString();
}

async function getDiscovery(): Promise<DiscoveryDocument> {
  if (!discoveryPromise) {
    discoveryPromise = fetch(
      `${getIssuer()}.well-known/openid-configuration`,
    ).then(async (res) => {
      if (!res.ok) {
        discoveryPromise = null;
        throw new Error(`Auth0 discovery falhou: ${res.status}`);
      }
      return (await res.json()) as DiscoveryDocument;
    });
  }
  return discoveryPromise;
}

export async function buildAuthorizeUrl(params: {
  state: string;
  nonce: string;
  codeChallenge: string;
  screenHint?: string | null;
  loginHint?: string | null;
}): Promise<string> {
  const { authorization_endpoint } = await getDiscovery();
  const url = new URL(authorization_endpoint);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('client_id', AUTH0_CLIENT_ID);
  url.searchParams.set('redirect_uri', callbackUrl());
  url.searchParams.set('scope', AUTH0_SCOPE);
  url.searchParams.set('state', params.state);
  url.searchParams.set('nonce', params.nonce);
  url.searchParams.set('code_challenge', params.codeChallenge);
  url.searchParams.set('code_challenge_method', 'S256');
  if (AUTH0_AUDIENCE) url.searchParams.set('audience', AUTH0_AUDIENCE);
  if (params.screenHint) url.searchParams.set('screen_hint', params.screenHint);
  if (params.loginHint) url.searchParams.set('login_hint', params.loginHint);
  return url.toString();
}

export async function exchangeCode(
  code: string,
  codeVerifier: string,
): Promise<{ id_token?: string; access_token?: string }> {
  const { token_endpoint } = await getDiscovery();
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: AUTH0_CLIENT_ID,
    client_secret: AUTH0_CLIENT_SECRET,
    code,
    code_verifier: codeVerifier,
    redirect_uri: callbackUrl(),
  });

  const res = await fetch(token_endpoint, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body,
  });

  if (!res.ok) {
    throw new Error(`Troca de code falhou: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as { id_token?: string; access_token?: string };
}

export async function verifyIdToken(
  idToken: string,
  nonce: string,
): Promise<Auth0User> {
  if (!jwks) {
    const { jwks_uri } = await getDiscovery();
    jwks = createRemoteJWKSet(new URL(jwks_uri));
  }

  const { payload } = await jwtVerify(idToken, jwks, {
    issuer: getIssuer(),
    audience: AUTH0_CLIENT_ID,
  });

  if (payload.nonce !== nonce) {
    throw new Error('nonce inválido');
  }

  return toUser(payload);
}

export function buildLogoutUrl(returnTo: string): string {
  const url = new URL(`https://${AUTH0_DOMAIN}/v2/logout`);
  url.searchParams.set('client_id', AUTH0_CLIENT_ID);
  url.searchParams.set('returnTo', returnTo);
  return url.toString();
}

function toUser(payload: JWTPayload): Auth0User {
  const pick = (key: string) =>
    typeof payload[key] === 'string' ? (payload[key] as string) : undefined;

  return {
    sub: String(payload.sub),
    name: pick('name'),
    nickname: pick('nickname'),
    email: pick('email'),
    picture: pick('picture'),
  };
}
