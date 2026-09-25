import type { APIRoute } from 'astro';
import { SITE_URL } from 'astro:env/server';
import { buildLogoutUrl } from '../../../lib/auth0';
import { clearSession } from '../../../lib/session';

export const prerender = false;

export const POST: APIRoute = async ({ cookies, redirect }) => {
  clearSession(cookies);
  return redirect(buildLogoutUrl(SITE_URL));
};
