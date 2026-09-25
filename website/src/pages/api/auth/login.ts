import type { APIRoute } from 'astro';
import { createHash, randomBytes } from 'node:crypto';
import { buildAuthorizeUrl, callbackUrl } from '../../../lib/auth0';
import { resolveRequestOrigin } from '../../../lib/origin';

export const prerender = false;

const TRANSIENT_MAX_AGE = 60 * 10;

export const GET: APIRoute = async ({ request, url, cookies, redirect }) => {
  const state = randomBytes(16).toString('hex');
  const nonce = randomBytes(16).toString('hex');
  const codeVerifier = randomBytes(32).toString('hex');
  const codeChallenge = createHash('sha256')
    .update(codeVerifier)
    .digest('base64url');

  const options = {
    httpOnly: true,
    secure: import.meta.env.PROD,
    sameSite: 'lax' as const,
    path: '/',
    maxAge: TRANSIENT_MAX_AGE,
  };

  cookies.set('linx_oauth_state', state, options);
  cookies.set('linx_oauth_nonce', nonce, options);
  cookies.set('linx_oauth_verifier', codeVerifier, options);

  const authorizeUrl = await buildAuthorizeUrl({
    state,
    nonce,
    codeChallenge,
    redirectUri: callbackUrl(resolveRequestOrigin(request, url)),
    screenHint: url.searchParams.get('screen_hint'),
    loginHint: url.searchParams.get('login_hint'),
  });

  return redirect(authorizeUrl);
};
