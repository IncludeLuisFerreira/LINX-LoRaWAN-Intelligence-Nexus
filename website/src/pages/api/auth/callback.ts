import type { APIRoute } from 'astro';
import { POST_LOGIN_REDIRECT } from 'astro:env/server';
import { callbackUrl, exchangeCode, verifyIdToken } from '../../../lib/auth0';
import { resolveRequestOrigin } from '../../../lib/origin';
import { safeRelativePath } from '../../../lib/redirect';
import { setSession } from '../../../lib/session';

export const prerender = false;

export const GET: APIRoute = async ({ request, url, cookies, redirect }) => {
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const oauthError = url.searchParams.get('error');

  const expectedState = cookies.get('linx_oauth_state')?.value;
  const nonce = cookies.get('linx_oauth_nonce')?.value;
  const codeVerifier = cookies.get('linx_oauth_verifier')?.value;

  cookies.delete('linx_oauth_state', { path: '/' });
  cookies.delete('linx_oauth_nonce', { path: '/' });
  cookies.delete('linx_oauth_verifier', { path: '/' });

  if (oauthError) {
    console.error('[auth/callback] Auth0 retornou erro:', oauthError);
    return new Response('Não foi possível concluir o login.', { status: 400 });
  }

  if (
    !code ||
    !state ||
    !expectedState ||
    state !== expectedState ||
    !nonce ||
    !codeVerifier
  ) {
    return new Response('Requisição de callback inválida.', { status: 400 });
  }

  try {
    const redirectUri = callbackUrl(resolveRequestOrigin(request, url));
    const tokens = await exchangeCode(code, codeVerifier, redirectUri);
    if (!tokens.id_token) throw new Error('id_token ausente');
    const user = await verifyIdToken(tokens.id_token, nonce);
    await setSession(cookies, user);
  } catch (err) {
    console.error('[auth/callback]', err);
    return new Response('Não foi possível concluir o login.', { status: 401 });
  }

  return redirect(safeRelativePath(POST_LOGIN_REDIRECT));
};
