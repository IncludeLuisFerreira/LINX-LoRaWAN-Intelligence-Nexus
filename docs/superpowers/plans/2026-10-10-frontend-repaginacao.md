# Repaginação do Frontend — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reescrever a UI do `frontend/` como um console de gestão limpo (estética ThingsBoard) com CRUD de Tenants, Applications e Devices contra o `identity_api`, sem login.

**Architecture:** SPA React 19 + Vite + Tailwind com navegação por drill-down (Tenants → Applications → Devices) e visão global de Devices. design system próprio em `src/components/ui/`, camada de dados em `src/services/`, hooks de fetch próprios. `react-hook-form` + `zod` em modais. Zero dependências de runtime novas; `@testing-library/react` + `jsdom` como devDependencies para atingir a meta de cobertura.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind, react-router-dom v7, axios, react-hook-form, zod, Vitest, MSW, Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-10-frontend-repaginacao-design.md`

## Global Constraints

- **Zero dependências de runtime novas.** (As dev-only de teste são permitidas e listadas no Task 1.)
- Stack fixa: React 19, Vite, TS, Tailwind, react-router-dom v7, axios, react-hook-form, zod, Vitest, MSW.
- `axios` baseURL = `/api/v1`; dev via proxy `vite` `/api` → `http://localhost:8000`.
- Sem login, sem auth, sem token de serviço, sem redirect 401.
- Device: somente Criar / Listar / Excluir (backend não tem PATCH).
- Device hex: `dev_eui` e `join_eui` = `^[0-9a-fA-F]{16}$`; `app_key` = `^[0-9a-fA-F]{32}$`.
- Nomes (tenant/app) mínimo 2 caracteres.
- Cobertura de testes > 70%.
- Não fazer `push` sem permissão.
- Tema claro: fundo `slate-50`, superfícies brancas, acento `primary` `#2563eb`.

## Review Focus

1. **Hex de device com caixa mista** (`AA:BB` inválido; `AABB...` maiúsculo aceito) — a validação zod aceita qualquer caixa, o backend normaliza. Testar maiúsculo válido e comprimento errado.
2. **Falha parcial de fetch em cascata** (um tenant sem apps, app sem devices, ou erro de rede em um ramo) — as listas não podem quebrar por inteiro; usar `Promise.allSettled`.
3. **Deep-link/refresh direto** em `/tenants/:id` e `/tenants/:id/applications/:appId` — o SPA fallback + refetch devem renderizar o workspace, não tela vazia.
4. **Device create com backend indisponível** (502 ChirpStack) — mostrar a mensagem real do backend e não inserir item fantasma na lista.
5. **Excluir tenant/app** — após confirmar, a lista afetada é refeita e o recurso some (sem estado otimista órfão).

---

### Task 1: Setup de teste e configuração base

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/.env.example`
- Test: `frontend/src/services/api.test.ts` (existente, ajustar)

**Interfaces:**
- Produces: `api` (axios instance) com `baseURL = '/api/v1'`; `getErrorMessage(error, fallback?) => string`. Sem interceptor de 401.

- [ ] **Step 1: Adicionar devDependencies de teste** (`@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `@vitest/coverage-v8`) sem alterar deps de runtime.

```bash
cd frontend && npm install -D @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @vitest/coverage-v8
```

- [ ] **Step 2: Configurar Vitest no `vite.config.ts`** — adicionar bloco `test`:

```ts
test: {
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
  globals: true,
  coverage: {
    provider: 'v8',
    reporter: ['text', 'lcov'],
    exclude: ['src/main.tsx', 'src/mocks/**', 'src/**/*.d.ts', 'src/test/**'],
  },
}
```
E `server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } }`.

- [ ] **Step 3: Criar `frontend/src/test/setup.ts`** com `import '@testing-library/jest-dom'`.

- [ ] **Step 4: Ajustar `api.ts`** — `baseURL = '/api/v1'`; remover o interceptor de resposta que limpa storage e redireciona para `/login`; manter `getErrorMessage`.

- [ ] **Step 5: Escrever teste de `getErrorMessage`** cobrindo `detail`, `message`, erro genérico e fallback. Rodar `cd frontend && npm test`. Expected: PASS.

- [ ] **Step 6: Rodar gates** `npm run lint && npx tsc -b`.

- [ ] **Step 7: Commit** `chore(frontend): configura vitest+testing-library e baseURL via proxy`.

---

### Task 2: Tokens de tema e estilos base

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: classes utilitárias `primary`, `surface`, `border`, `muted` disponíveis no Tailwind.

- [ ] **Step 1:** `extend.colors`: `primary` (50–900, 500=`#2563eb`), `surface` (`DEFAULT #ffffff`), `border` (`DEFAULT #e2e8f0`), `muted` (`DEFAULT #64748b`). `fontFamily.sans` = `Inter` + fallback.
- [ ] **Step 2:** Em `index.css`, `body { @apply bg-slate-50 text-slate-800; }` e importar fonte Inter via `@import url(...)` no topo (antes das diretivas Tailwind).
- [ ] **Step 3:** Rodar `npm run build`. Expected: build OK.
- [ ] **Step 4: Commit** `feat(frontend): tokens de tema claro e estilos base`.

---

### Task 3: Primitivos de UI — feedback e ação

**Files:**
- Create: `frontend/src/components/ui/Spinner.tsx`, `Alert.tsx`, `Badge.tsx`, `EmptyState.tsx`, `Button.tsx`
- Test: `frontend/src/components/ui/Button.test.tsx`

**Interfaces:**
- Produces:
  - `Button(props: {variant?: 'primary'|'secondary'|'danger'|'ghost'; loading?: boolean; disabled?: boolean} & ButtonHTMLAttributes<HTMLButtonElement>)`
  - `Spinner(props: {size?: 'sm'|'md'|'lg'; className?})`
  - `Alert(props: {variant: 'error'|'success'|'info'; children; onRetry?: () => void})`
  - `Badge(props: {children; color?: 'blue'|'gray'|'green'|'red'})`
  - `EmptyState(props: {title; description?; action?: ReactNode})`

- [ ] **Step 1: Teste do `Button`** — renderizar com texto, clicar chama `onClick`; com `loading` o botão fica `disabled` e mostra spinner. Usar `render`, `fireEvent`/`userEvent`.
- [ ] **Step 2: Rodar teste** `npm test -- Button.test.tsx` → FAIL (módulo inexistente).
- [ ] **Step 3: Implementar os 5 componentes** seguindo os padrões Tailwind do tema.
- [ ] **Step 4: Rodar teste** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): primitivos de UI (botão, spinner, alert, badge, empty)`.

---

### Task 4: Primitivos de UI — estrutura e dados

**Files:**
- Create: `frontend/src/components/ui/Card.tsx`, `StatCard.tsx`, `Input.tsx`, `Select.tsx`, `Table.tsx`, `Breadcrumbs.tsx`, `Tabs.tsx`
- Test: `frontend/src/components/ui/Tabs.test.tsx`

**Interfaces:**
- Produces:
  - `Card(props: {title?; action?: ReactNode; children})`
  - `StatCard(props: {label; value: number|string; icon?: ReactNode})`
  - `Input(props: InputHTMLAttributes<HTMLInputElement> & {label?; error?; register?: UseFormRegisterReturn})`
  - `Select(props: SelectHTMLAttributes<HTMLSelectElement> & {label?; error?; register?: UseFormRegisterReturn; options: {value;label}[]})`
  - `Table<T>(props: {columns: {key;header;render?:(row:T)=>ReactNode}[]; rows: T[]; rowKey:(row:T)=>string; empty?: ReactNode})`
  - `Breadcrumbs(props: {items: {label; to?}[]})`
  - `Tabs(props: {tabs: {id;label;content:ReactNode}[]; active; onChange})`

- [ ] **Step 1: Teste do `Tabs`** — renderiza tabs, clica e chama `onChange` com o id e mostra o conteúdo ativo.
- [ ] **Step 2: Rodar teste** → FAIL.
- [ ] **Step 3: Implementar componentes.**
- [ ] **Step 4: Rodar teste** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): primitivos de estrutura e dados`.

---

### Task 5: Modal e diálogo de confirmação

**Files:**
- Create: `frontend/src/components/ui/Modal.tsx`, `ConfirmDialog.tsx`
- Test: `frontend/src/components/ui/ConfirmDialog.test.tsx`

**Interfaces:**
- Produces:
  - `Modal(props: {open; onClose; title; children; footer?:ReactNode})` — fecha no `Esc`/overlay.
  - `ConfirmDialog(props: {open; title; message; confirmLabel?; danger?; loading?; onConfirm; onCancel})`
- Consumes: `Button` (Task 3).

- [ ] **Step 1: Teste do `ConfirmDialog`** — com `open`, mostra título/mensagem; clicar "Excluir" chama `onConfirm`; clicar "Cancelar" chama `onCancel`.
- [ ] **Step 2: Rodar teste** → FAIL.
- [ ] **Step 3: Implementar `Modal` e `ConfirmDialog`** usando portal (`createPortal`).
- [ ] **Step 4: Rodar teste** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): modal e confirmação de exclusão`.

---

### Task 6: Ícones inline

**Files:**
- Create: `frontend/src/components/ui/icons/index.tsx`

**Interfaces:**
- Produces: componentes `Plus, Trash, Edit, ChevronRight, Menu, Building, Layers, Cpu, Search, Refresh, Close` (props `{className?: string}`).

- [ ] **Step 1:** Implementar cada ícone como SVG `currentColor` (`w-5 h-5` default via `className`).
- [ ] **Step 2:** Rodar `npx tsc -b`. Expected: OK.
- [ ] **Step 3: Commit** `feat(frontend): conjunto de ícones inline`.

---

### Task 7: Layout (AppShell, Sidebar, Topbar), rotas e remoção do login

**Files:**
- Create: `frontend/src/components/layout/AppShell.tsx`, `Sidebar.tsx`, `Topbar.tsx`
- Modify: `frontend/src/routes.tsx`
- Delete: `frontend/src/pages/Login.tsx`, `frontend/src/services/auth.ts`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AppDetail.tsx`, `frontend/src/pages/Devices.tsx`, `frontend/src/pages/Tenants.tsx`, `frontend/src/pages/app/NewApp.tsx`, `frontend/src/pages/tenants/NewTenant.tsx`
- Test: `frontend/src/components/layout/Sidebar.test.tsx`

**Interfaces:**
- Produces: `AppShell` (usa `<Outlet/>`, renderiza `Sidebar` + `Topbar` com `breadcrumbs` via contexto de rota). `Sidebar` com itens `Tenants` (`/tenants`) e `Devices` (`/devices`), acesso aos itens por `role="link"`.
- Consumes: `Breadcrumbs`, ícones.

- [ ] **Step 1: Teste do `Sidebar`** — renderiza links "Tenants" e "Devices" com os `href` corretos (envolver em `MemoryRouter`).
- [ ] **Step 2: Rodar teste** → FAIL.
- [ ] **Step 3: Implementar layout**; rotas:
```
/ → <Navigate to="/tenants" replace/>
<Route element={<AppShell/>}>
  /tenants → TenantListPage
  /tenants/:tenantId → TenantDetailPage
  /tenants/:tenantId/applications/:appId → ApplicationDetailPage
  /devices → DeviceListPage
  * → NotFound
</Route>
```
Remover rotas/páginas de Login. Como as páginas novas ainda não existem, nesta task criar arquivos placeholder export default que serão substituídos nas tasks seguintes.

- [ ] **Step 4: Rodar teste** → PASS; `npx tsc -b`.
- [ ] **Step 5: Commit** `feat(frontend): app shell, sidebar, topbar e novo roteamento`.

---

### Task 8: Serviço de Tenant com CRUD completo

**Files:**
- Modify: `frontend/src/services/tenant.ts`
- Test: `frontend/src/services/tenant.test.ts`

**Interfaces:**
- Produces: `tenantService.create(input)`, `.list(opts?)`, `.get(id)`, `.update(id,input)`, `.remove(id)`; tipos `TenantOutput`, `CreateTenantInput`, `UpdateTenantInput`.
- Consumes: `api` (Task 1).

- [ ] **Step 1: Teste** com `vi.mock('./api')` — verifica método HTTP e URL de cada operação (`POST /tenant/`, `GET /tenant`, `GET /tenant/{id}`, `PATCH /tenant/{id}`, `DELETE /tenant/{id}`) e parse do body.
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar** os 5 métodos.
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): CRUD completo de tenant`.

---

### Task 9: Serviço de Application com CRUD completo

**Files:**
- Modify: `frontend/src/services/app.ts`
- Test: `frontend/src/services/app.test.ts`

**Interfaces:**
- Produces: `applicationService.create(tenantId,input)`, `.listByTenant(tenantId)`, `.get(tenantId,appId)`, `.update(tenantId,appId,input)`, `.remove(tenantId,appId)`; `loadApplicationsByTenant(tenants, fetch?)`.
- Consumes: `api`.

- [ ] **Step 1: Teste** — URLs `POST/GET /tenant/{tid}/applications`, `GET/PATCH/DELETE .../applications/{aid}`; e `loadApplicationsByTenant` tolera rejeição (`Promise.allSettled`).
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): CRUD completo de application`.

---

### Task 10: Serviço de Device

**Files:**
- Create: `frontend/src/services/device.ts`
- Test: `frontend/src/services/device.test.ts`

**Interfaces:**
- Produces: `deviceService.listByApp(appId)`, `.create(input)`, `.remove(id)`; `DeviceOutput`, `CreateDeviceInput`.
- Consumes: `api`.

- [ ] **Step 1: Teste** — `GET /devices?app_id=`, `POST /devices`, `DELETE /devices/{id}`.
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): serviço de device`.

---

### Task 11: Hook `useAsyncData` e utilitários

**Files:**
- Create: `frontend/src/hooks/useAsyncData.ts`, `frontend/src/lib/format.ts`
- Test: `frontend/src/hooks/useAsyncData.test.tsx`, `frontend/src/lib/format.test.ts`

**Interfaces:**
- Produces:
  - `useAsyncData<T>(fn: () => Promise<T>, deps: unknown[]): { data: T | null; error: string; loading: boolean; reload: () => void }`
  - `formatDate(iso: string): string` (pt-BR, ex. `10/10/2026 14:30`); `cn(...parts: (string|false|undefined)[]): string`.
- Consumes: `getErrorMessage`.

- [ ] **Step 1: Teste do hook** com componente de teste — loading→data; fn rejeitando→error; `reload` refaz.
- [ ] **Step 2: Teste do `formatDate`** — ISO válido e string vazia (`'—'`).
- [ ] **Step 3: Rodar** → FAIL.
- [ ] **Step 4: Implementar.**
- [ ] **Step 5: Rodar** → PASS.
- [ ] **Step 6: Commit** `feat(frontend): hook useAsyncData e utilitários`.

---

### Task 12: Página de lista de Tenants

**Files:**
- Create: `frontend/src/pages/tenants/TenantListPage.tsx`
- Test: `frontend/src/pages/tenants/TenantListPage.test.tsx`

**Interfaces:**
- Consumes: `tenantService.list`, `loadApplicationsByTenant`, `useAsyncData`, `Card`, `StatCard`, `Modal`, `Button`, `ConfirmDialog`, `EmptyState`, `Alert`, `Spinner`; `react-hook-form`+`zod`.
- Produces: rota `/tenants` funcional (cada card linka para `/tenants/:id`); criação via modal; edição e exclusão.

- [ ] **Step 1: Teste** (MSW handlers de tenant) — renderiza cards de tenants; botão "Novo Tenant" abre modal; submeter cria e re-lista; estado vazio mostra `EmptyState`.
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar** com header (título + botão), grid de `Card` mostrando nome, descrição e contagem de apps.
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): página de lista de tenants`.

---

### Task 13: Workspace do Tenant (applications + configurações)

**Files:**
- Create: `frontend/src/pages/tenants/TenantDetailPage.tsx`, `frontend/src/pages/applications/ApplicationList.tsx`
- Test: `frontend/src/pages/tenants/TenantDetailPage.test.tsx`

**Interfaces:**
- Consumes: `tenantService.get/update/remove`, `applicationService.listByTenant/create`, `useAsyncData`, `Tabs`, `Breadcrumbs`, `Modal`, `ConfirmDialog`.
- Produces: rota `/tenants/:tenantId` — tab `Applications` (lista + criar) e tab `Configurações` (editar/excluir tenant). Excluir tenant navega de volta para `/tenants`.

- [ ] **Step 1: Teste** — com handlers MSW, deep-link renderiza nome do tenant e lista apps; criar app atualiza lista; excluir tenant chama `tenantService.remove`.
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): workspace do tenant`.

---

### Task 14: Workspace da Application (devices + configurações)

**Files:**
- Create: `frontend/src/pages/applications/ApplicationDetailPage.tsx`, `frontend/src/pages/applications/DeviceFormModal.tsx`
- Test: `frontend/src/pages/applications/ApplicationDetailPage.test.tsx`

**Interfaces:**
- Consumes: `applicationService.get/update/remove`, `deviceService.listByApp/create/remove`, `useAsyncData`, `Tabs`.
- Produces: rota `/tenants/:tenantId/applications/:appId` — tab `Devices` (lista + criar com `DeviceFormModal`) e tab `Configurações` (editar/excluir app). `DeviceFormModal` valida hex (Review Focus 1).
- `DeviceFormModal` props: `{ open; appId: string; onClose; onCreated }`.

- [ ] **Step 1: Teste** — deep-link renderiza app e devices; `DeviceFormModal` rejeita `dev_eui` curto e aceita maiúsculo válido; criar device chama `deviceService.create` com payload correto; erro 502 mostra `Alert` (Review Focus 4).
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar** com schema zod:
```ts
const deviceSchema = z.object({
  dev_eui: z.string().regex(/^[0-9a-fA-F]{16}$/, 'Deve ter 16 caracteres hexadecimais'),
  join_eui: z.string().regex(/^[0-9a-fA-F]{16}$/, 'Deve ter 16 caracteres hexadecimais'),
  app_key: z.string().regex(/^[0-9a-fA-F]{32}$/, 'Deve ter 32 caracteres hexadecimais'),
});
```
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): workspace da application e formulário de device`.

---

### Task 15: Visão global de Devices

**Files:**
- Create: `frontend/src/pages/devices/DeviceListPage.tsx`
- Test: `frontend/src/pages/devices/DeviceListPage.test.tsx`

**Interfaces:**
- Consumes: `tenantService.list`, `applicationService.listByTenant`, `deviceService.listByApp/create/remove`, `Table`, `Modal`.
- Produces: rota `/devices` — tabela flat de todos os devices (dev_eui, join_eui, application, tenant, criado em, ações); criar com select tenant→app; excluir.
- Abordagem: carregar tenants, depois apps por tenant, depois devices por app, com `Promise.allSettled` (Review Focus 2).

- [ ] **Step 1: Teste** — renderiza devices agregados; um tenant/app com falha não quebra a tabela inteira; criar exige seleção de app.
- [ ] **Step 2: Rodar** → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): visão global de devices`.

---

### Task 16: Handlers MSW, docs e verificação final

**Files:**
- Modify: `frontend/src/mocks/handlers.ts`, `frontend/README.md`
- Test: `frontend/src/mocks/handlers.test.ts`

**Interfaces:**
- Produces: handlers MSW cobrindo tenant/app (alinhados) + devices (`GET /api/v1/devices`, `POST /api/v1/devices`, `DELETE /api/v1/devices/:id`).

- [ ] **Step 1:** Adicionar handlers de devices com estado em memória e validação de hex/duplicata (409).
- [ ] **Step 2: Estender `handlers.test.ts`** para devices.
- [ ] **Step 3:** Atualizar `README.md` (estrutura, remoção do login, proxy `/api`, fluxo de telas).
- [ ] **Step 4: Rodar suites de verificação:**
  - `cd frontend && npm run lint`
  - `npx tsc -b`
  - `npm run build`
  - `npm test -- --coverage` → garantir cobertura > 70%.
- [ ] **Step 5: Commit** `test(frontend): handlers de MSW de device, docs e cobertura`.

---

## Self-Review

- **Cobertura do spec:** navegação drill-down (Tasks 12–15), design system (3–6), camada de dados (8–11), rotas/layout e remoção de login (7), tema claro (2), proxy/baseURL (1), MSW/docs (16), estados de UX distribuídos em 12–15. Sem lacunas.
- **Consistência de tipos:** `DeviceOutput.app_id`, `applicationService.listByTenant(tenantId)`, `useAsyncData` com `deps` array — usados de forma idêntica nas tasks 10–15.
- **Review Focus:** cada um dos 5 itens mapeado a um teste (Tasks 14, 15, 13, 14, 13).
- **Proporção:** plano em nível de tarefa, sem transcrever corpos completos.
