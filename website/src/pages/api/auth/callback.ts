import type { APIRoute } from 'astro';
import { APP_URL } from 'astro:env/server';
import { exchangeCode, verifyIdToken } from '../../../lib/auth0';
import { setSession } from '../../../lib/session';

export const prerender = false;

export const GET: APIRoute = async ({ url, cookies, redirect }) => {
  const oauthError = url.searchParams.get('error');
  if (oauthError) {
    return new Response(`Falha na autenticação: ${oauthError}`, { status: 400 });
  }

  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const expectedState = cookies.get('linx_oauth_state')?.value;
  const nonce = cookies.get('linx_oauth_nonce')?.value;
  const codeVerifier = cookies.get('linx_oauth_verifier')?.value;

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
    const tokens = await exchangeCode(code, codeVerifier);
    if (!tokens.id_token) throw new Error('id_token ausente');
    const user = await verifyIdToken(tokens.id_token, nonce);
    await setSession(cookies, user);
  } catch (err) {
    console.error('[auth/callback]', err);
    return new Response('Não foi possível concluir o login.', { status: 401 });
  }

  cookies.delete('linx_oauth_state', { path: '/' });
  cookies.delete('linx_oauth_nonce', { path: '/' });
  cookies.delete('linx_oauth_verifier', { path: '/' });

  return redirect(APP_URL);
};
