import type { APIRoute } from 'astro';
import { getSession } from '../../../lib/session';

export const prerender = false;

export const GET: APIRoute = async ({ cookies }) => {
  const user = await getSession(cookies);

  if (!user) {
    return new Response(JSON.stringify({ user: null }), {
      status: 401,
      headers: { 'content-type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({ user }), {
    status: 200,
    headers: {
      'content-type': 'application/json',
      'cache-control': 'no-store',
    },
  });
};
