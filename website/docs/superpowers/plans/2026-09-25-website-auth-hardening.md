# Website Auth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Endurecer o fluxo Auth0 do website (sessão só do website, redirect seguro, erro não vazado, testes automatizados e CI).

**Architecture:** O cookie de sessão (`linx_session`) pertence apenas ao domínio do website. O callback deixa de redirecionar para `APP_URL` e passa a redirecionar para um caminho same-origin configurável via `POST_LOGIN_REDIRECT`. Testes unitários em Vitest exercitam `lib/` e os handlers `GET`/`POST` das rotas `/api/auth/*`, com `astro:env/server` resolvido por alias para um stub.

**Tech Stack:** Astro 7, `@astrojs/node` (standalone), `jose`, Vitest, Node 22.

---

## File Structure

- Create: `website/vitest.config.ts` — configuração do Vitest + alias de env.
- Create: `website/src/test/env.ts` — valores de env para os testes.
- Create: `website/src/test/context.ts` — helpers de `AstroCookies` e `APIContext` mockados.
- Create: `website/src/lib/redirect.ts` — saneamento do destino pós-login.
- Create: `website/src/lib/redirect.test.ts`
- Create: `website/src/lib/session.test.ts`
- Create: `website/src/lib/auth0.test.ts`
- Create: `website/src/pages/api/auth/login.test.ts`
- Create: `website/src/pages/api/auth/callback.test.ts`
- Create: `website/src/pages/api/auth/logout.test.ts`
- Create: `website/src/pages/api/auth/me.test.ts`
- Create: `website/src/astro.config.test.ts` — garante `security.checkOrigin`.
- Create: `.github/workflows/website-ci.yml`
- Modify: `website/src/pages/api/auth/callback.ts`
- Modify: `website/astro.config.mjs`
- Modify: `website/.env.example`
- Modify: `website/package.json`
- Modify: `website/README.md`

---

### Task 1: Configurar Vitest

**Files:**
- Create: `website/vitest.config.ts`
- Create: `website/src/test/env.ts`
- Create: `website/src/test/context.ts`
- Modify: `website/package.json`

- [ ] **Step 1: Criar stub de env**

`website/src/test/env.ts`:

```ts
export const AUTH0_DOMAIN = 'tenant.example.auth0.com';
export const AUTH0_CLIENT_ID = 'test-client-id';
export const AUTH0_CLIENT_SECRET = 'test-client-secret';
export const AUTH0_AUDIENCE = '';
export const AUTH0_SCOPE = 'openid profile email';
export const SITE_URL = 'http://localhost:4321';
export const POST_LOGIN_REDIRECT = '/';
export const SESSION_SECRET = 'test-session-secret-com-32-caracteres-ou-mais';
```

- [ ] **Step 2: Criar helpers de contexto**

`website/src/test/context.ts`:

```ts
import type { AstroCookies } from 'astro';

export function createCookies(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  const cookies = {
    get: (name: string) => {
      const value = store.get(name);
      return value === undefined ? undefined : { value };
    },
    set: (name: string, value: string) => {
      store.set(name, value);
    },
    delete: (name: string) => {
      store.delete(name);
    },
  } as unknown as AstroCookies;
  return { cookies, store };
}

export function createRedirect() {
  return (location: string, status = 302) =>
    new Response(null, { status, headers: { location } });
}
```

- [ ] **Step 3: Criar configuração do Vitest**

`website/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  resolve: {
    alias: {
      'astro:env/server': fileURLToPath(
        new URL('./src/test/env.ts', import.meta.url),
      ),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
```

- [ ] **Step 4: Adicionar scripts e devDependency**

Adicionar em `website/package.json`:

```json
"scripts": {
  "test": "vitest",
  "test:run": "vitest run"
}
```

E `vitest` em `devDependencies`.

- [ ] **Step 5: Instalar e verificar**

Run: `npm install` em `website/`
Expected: `vitest` instalado sem erros.

---

### Task 2: Testes de `session.ts`

**Files:**
- Create: `website/src/lib/session.test.ts`

- [ ] **Step 1: Escrever os testes**

Casos: round-trip `setSession`/`getSession`; token adulterado retorna `null`; sem cookie retorna `null`; sessão expirada retorna `null`; `clearSession` remove o cookie; `cookieOptions` tem `httpOnly`, `sameSite: 'lax'` e `path: '/'`.

- [ ] **Step 2: Rodar**

Run: `npm run test:run -- src/lib/session.test.ts`
Expected: PASS.

---

### Task 3: Testes de `auth0.ts`

**Files:**
- Create: `website/src/lib/auth0.test.ts`

- [ ] **Step 1: Escrever os testes**

Com `jose` gerando um par RSA e `fetch` mockado para servir `openid-configuration`, JWKS e `token_endpoint`:

- `buildAuthorizeUrl` inclui `response_type=code`, `client_id`, `redirect_uri`, `scope`, `state`, `nonce`, `code_challenge` e `code_challenge_method=S256`; inclui `audience` só quando configurado.
- `exchangeCode` lança quando `token_endpoint` responde não-2xx.
- `verifyIdToken` aceita token válido e rejeita `nonce` divergente e assinatura inválida.

- [ ] **Step 2: Rodar**

Run: `npm run test:run -- src/lib/auth0.test.ts`
Expected: PASS.

---

### Task 4: Redirect seguro + correção do callback

**Files:**
- Create: `website/src/lib/redirect.ts`
- Create: `website/src/lib/redirect.test.ts`
- Modify: `website/src/pages/api/auth/callback.ts`

- [ ] **Step 1: Teste do helper**

`redirect.test.ts` cobre: `undefined`/vazio → `/`; caminho relativo `/obrigado` preservado; `//evil.com`, `https://evil.com`, `\evil.com` e caracteres de controle → `/`.

- [ ] **Step 2: Implementar `redirect.ts`**

```ts
export function safeRelativePath(
  value: string | null | undefined,
  fallback = '/',
): string {
  if (!value) return fallback;
  if (!value.startsWith('/') || value.startsWith('//')) return fallback;
  if (value.includes('\\') || /[\u0000-\u001f]/.test(value)) return fallback;
  return value;
}
```

- [ ] **Step 3: Corrigir `callback.ts`**

- Importar `POST_LOGIN_REDIRECT` de `astro:env/server` e `safeRelativePath`.
- Ler e apagar os cookies transitórios (`linx_oauth_state`, `linx_oauth_nonce`, `linx_oauth_verifier`) em todos os caminhos.
- `oauthError`: `console.error` + resposta genérica `Não foi possível concluir o login.` (400).
- Sucesso: `redirect(safeRelativePath(POST_LOGIN_REDIRECT))`.

- [ ] **Step 4: Rodar**

Run: `npm run test:run -- src/lib/redirect.test.ts`
Expected: PASS.

---

### Task 5: Testes das rotas + `checkOrigin`

**Files:**
- Create: `website/src/pages/api/auth/login.test.ts`
- Create: `website/src/pages/api/auth/callback.test.ts`
- Create: `website/src/pages/api/auth/logout.test.ts`
- Create: `website/src/pages/api/auth/me.test.ts`
- Create: `website/src/astro.config.test.ts`
- Modify: `website/astro.config.mjs`

- [ ] **Step 1: Testes das rotas**

Invocando os handlers diretamente com contexto mockado:

- **login:** grava 3 cookies (`state`, `nonce`, `verifier`) e redireciona para a URL de authorize.
- **callback:** falta de `state`/`code` → 400; `state` divergente → 400; falha na troca/sessão → 401; sucesso → 302 para `POST_LOGIN_REDIRECT` e cookie de sessão gravado.
- **logout:** limpa a sessão e redireciona para o logout do Auth0.
- **me:** 401 com `{ user: null }` sem sessão; 200 com `{ user }` e `cache-control: no-store` com sessão.

- [ ] **Step 2: Tornar `checkOrigin` explícito**

Em `astro.config.mjs`, adicionar `security: { checkOrigin: true }` e trocar `APP_URL` por `POST_LOGIN_REDIRECT` (opcional, default `'/'`).

- [ ] **Step 3: Testar a config**

`astro.config.test.ts` importa o default export e afirma `security.checkOrigin === true`.

- [ ] **Step 4: Rodar**

Run: `npm run test:run`
Expected: todos os testes PASS.

---

### Task 6: Env, docs e CI

**Files:**
- Modify: `website/.env.example`
- Modify: `website/README.md`
- Create: `.github/workflows/website-ci.yml`

- [ ] **Step 1: Atualizar `.env.example`**

Substituir `APP_URL=https://app.exemplo.com` por `POST_LOGIN_REDIRECT=/` e documentar que a sessão é exclusiva do website.

- [ ] **Step 2: Documentar no README**

Seção de auth: sessão host-only do website; `POST_LOGIN_REDIRECT`; integração com o app é trabalho futuro.

- [ ] **Step 3: Criar CI**

Workflow `website-ci` com Node 22, `npm ci`, `npm run test:run` e `npm run build`, em `working-directory: ./website`, disparado por `website/**`.

---

### Task 7: Verificação final

- [ ] `npm run test:run` — todos passam.
- [ ] `npm run build` — build standalone conclui.
- [ ] `node ./dist/server/entry.mjs` + smoke das rotas `/api/auth/{login,callback,logout,me}`.
- [ ] `git status` — sem `.env` ou segredos rastreados.
