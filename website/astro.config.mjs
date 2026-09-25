// @ts-check
import { defineConfig, envField } from 'astro/config';
import node from '@astrojs/node';
import vercel from '@astrojs/vercel';

// Na Vercel usamos o adapter oficial (Build Output API + funções).
// Fora dela (Docker/nginx/VPS) mantemos o servidor Node standalone.
const isVercel = Boolean(process.env.VERCEL);

// https://astro.build/config
export default defineConfig({
  // A home e as páginas de marketing continuam estáticas (prerender).
  // Apenas as rotas /api/auth/* optam por renderização sob demanda.
  output: 'static',
  adapter: isVercel ? vercel() : node({ mode: 'standalone' }),
  // Protege rotas sob demanda contra requisições cross-origin (CSRF).
  // Explícito para não depender do default entre versões do Astro.
  security: { checkOrigin: true },
  env: {
    schema: {
      AUTH0_DOMAIN: envField.string({ context: 'server', access: 'secret' }),
      AUTH0_CLIENT_ID: envField.string({ context: 'server', access: 'secret' }),
      AUTH0_CLIENT_SECRET: envField.string({ context: 'server', access: 'secret' }),
      AUTH0_AUDIENCE: envField.string({
        context: 'server',
        access: 'secret',
        optional: true,
      }),
      AUTH0_SCOPE: envField.string({
        context: 'server',
        access: 'secret',
        default: 'openid profile email',
      }),
      POST_LOGIN_REDIRECT: envField.string({
        context: 'server',
        access: 'secret',
        optional: true,
        default: '/',
      }),
      // Origens extras (separadas por vírgula) autorizadas a iniciar o OAuth,
      // além do SITE_URL e dos domínios VERCEL_*.
      ALLOWED_ORIGINS: envField.string({
        context: 'server',
        access: 'secret',
        optional: true,
        default: '',
      }),
      SITE_URL: envField.string({ context: 'server', access: 'secret' }),
      SESSION_SECRET: envField.string({
        context: 'server',
        access: 'secret',
        min: 32,
      }),
    },
  },
});
