import type { APIRoute } from 'astro';
import { buildLogoutUrl } from '../../../lib/auth0';
import { resolveRequestOrigin } from '../../../lib/origin';
import { clearSession } from '../../../lib/session';

export const prerender = false;

export const POST: APIRoute = async ({ request, url, cookies, redirect }) => {
  clearSession(cookies);
  const returnTo = resolveRequestOrigin(request, url);
  return redirect(buildLogoutUrl(returnTo));
};
