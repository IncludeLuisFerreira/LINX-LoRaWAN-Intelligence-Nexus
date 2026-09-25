// @ts-check
import { defineConfig, envField } from 'astro/config';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  // A home e as páginas de marketing continuam estáticas (prerender).
  // Apenas as rotas /api/auth/* optam por renderização sob demanda.
  output: 'static',
  adapter: node({ mode: 'standalone' }),
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
      APP_URL: envField.string({ context: 'server', access: 'secret' }),
      SITE_URL: envField.string({ context: 'server', access: 'secret' }),
      SESSION_SECRET: envField.string({
        context: 'server',
        access: 'secret',
        min: 32,
      }),
    },
  },
});
