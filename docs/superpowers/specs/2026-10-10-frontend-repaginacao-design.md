# Repaginação do `frontend/`: console de gestão estilo ThingsBoard

- **Data:** 2026-10-10
- **Status:** Proposto
- **Escopo:** Reescrever a UI do `frontend/` para um console limpo e
  profissional (referência estética: ThingsBoard), conectado ao
  `identity_api` do `linx_core`, permitindo CRUD de Tenants, Applications e
  Devices sem login.

## Contexto

O `frontend/` é uma SPA em React 19 + Vite + TypeScript + Tailwind, com
`react-router-dom` v7, `axios`, `react-hook-form` + `zod` e MSW para mock.
Hoje é um esqueleto funcional, porém:

- Várias páginas são placeholders (`Devices.tsx`, `Dashboard.tsx`,
  `AppDetail.tsx` retornam só um `<div>`).
- Estilos inconsistentes: `Tenants.tsx` usa `gray-800`, `NewTenant.tsx` usa
  card branco, o layout usa `slate-950`. Sem design system.
- Existe um fluxo de `Login` mockado (`services/auth.ts` grava
  `accessToken`/`user` no `localStorage`) e o `axios` redireciona para
  `/login` em 401. Não há autenticação real.
- O `vite.config.ts` não tem proxy; o `axios` aponta para
  `http://localhost:8000/api/v1`, exigindo CORS no backend.

O `identity_api` já expõe CRUD via REST. O objetivo é reconstruir a UI em cima
desse contrato real, com hierarquia Tenant → Application → Device e estética
de console de gestão.

### Contrato real da API consumida

Base: `/api/v1` (via proxy do dev server; em produção o nginx já encaminha
`/api/` para `BACKEND_URL`).

| Método | Rota | Corpo / Params |
| --- | --- | --- |
| POST | `/api/v1/tenant/` | `{name, description?}` → 201 |
| GET | `/api/v1/tenant` | query `skip`, `limit` → lista |
| GET | `/api/v1/tenant/{tenant_id}` | → tenant |
| PATCH | `/api/v1/tenant/{tenant_id}` | `{name?, description?}` |
| DELETE | `/api/v1/tenant/{tenant_id}` | → 204 |
| POST | `/api/v1/tenant/{tenant_id}/applications` | `{name, description?}` → 201 |
| GET | `/api/v1/tenant/{tenant_id}/applications` | → lista |
| GET | `/api/v1/tenant/{tenant_id}/applications/{application_id}` | → app |
| PATCH | `/api/v1/tenant/{tenant_id}/applications/{application_id}` | `{name?, description?}` |
| DELETE | `/api/v1/tenant/{tenant_id}/applications/{application_id}` | → 204 |
| GET | `/api/v1/devices?app_id=` | → lista |
| POST | `/api/v1/devices` | `{dev_eui, app_id, join_eui, app_key}` → 201 |
| DELETE | `/api/v1/devices/{device_id}` | → 204 |

Observações do contrato:

- **Device não tem PATCH.** O CRUD de device é Criar / Listar / Excluir.
- Device create valida hex: `dev_eui` e `join_eui` com 16 hex, `app_key` com
  32 hex. O backend normaliza para minúsculas.
- As rotas do `identity_api` **não** exigem `X-Service-Token` hoje; o front
  chama direto.
- `TenantResponse` inclui `id`, `name`, `description`, `created_at`,
  `updated_at`. Ids são UUID.

## Objetivos

1. Reescrever a UI em um console limpo, consistente e profissional, com
   estética de referência do ThingsBoard (fundo claro, cards brancos, acento
   azul, sidebar + topbar com breadcrumbs).
2. Navegação hierárquica com drill-down: Tenants → Applications → Devices,
   mais uma visão global de Devices.
3. CRUD completo (respeitando o limite do contrato) contra o `identity_api`,
   sem login e sem token de serviço.
4. Estados de UX previsíveis em toda tela: loading, erro com retry, vazio
   com CTA.
5. Manter a stack atual e **não adicionar dependências novas**.

## Não-objetivos

- Autenticação, autorização, RBAC ou token de serviço. Segurança fica para
  um trabalho futuro.
- Alterar o backend (`identity_api` ou `linx_shared`). O contrato é fixo.
- Adicionar edição de device (o backend não tem PATCH).
- Gráficos/telemetria, dashboard de métricas ou editor de rule chains.
- Migrar para o stack do ThingsBoard (Angular/Material). Copiamos apenas a
  estética e o modelo de navegação.
- Substituir o MSW ou o pipeline de CI já existentes.

## Design

### 1. Arquitetura e stack

- Stack mantida: React 19, Vite, TypeScript, Tailwind, `react-router-dom` v7,
  `axios`, `react-hook-form` + `zod`, Vitest + MSW.
- **Zero dependências novas.** Ícones por componentes SVG inline próprios em
  `src/components/ui/icons/`. (Troca fácil por `lucide-react` depois, se
  desejado — decisão futura.)
- Estado local + hooks próprios de fetch. Sem Redux e sem
  `@tanstack/react-query`.
- Formulários de criação/edição em modais com `react-hook-form` + `zod`.

### 2. Navegação e rotas

```
/                         → redirect /tenants
/tenants                  → lista de tenants (cards com contagem de apps)
/tenants/:tenantId        → workspace do tenant
     tab Applications     → lista de apps + criar/editar/excluir
     tab Configuracoes    → editar/excluir tenant
/tenants/:tenantId/applications/:appId
     tab Devices          → lista de devices do app + criar/excluir
     tab Configuracoes    → editar/excluir app
/devices                  → lista global de devices (cross-tenant)
```

- Login removido. `/` cai direto em `/tenants`.
- Topbar exibe breadcrumb em cada nível:
  `Tenants / {tenant.name} / {app.name}`.
- Tabs por workspace (Application lista; Configurações edita).
- Rota não encontrada → `NotFound`.

### 3. Layout e design system

- `AppShell` = Sidebar fixa (240px) + Topbar + `<main>` rolável.
- Sidebar: logo "LINX" e itens de nav **Tenants** e **Devices**.
  Menu mobile colapsável (overlay) reaproveitando o padrão atual.
- Topbar: botão de menu (mobile), breadcrumbs, ações contextuais (ex.:
  "Novo Tenant", "Nova Application", "Novo Device").
- Tokens de tema em `tailwind.config.js` (`extend.colors`): `primary`
  (azul `#2563eb` e variações), `surface`, `border`, `muted`. Fundo geral
  `slate-50`; superfícies brancas `rounded-lg border shadow-sm`.
- UI kit em `src/components/ui/`:
  - `Button` (variantes `primary`, `secondary`, `danger`, `ghost`; estados
    `loading`/`disabled`).
  - `Card`, `StatCard`, `Badge`, `Input`, `Select`, `Table`, `Modal`,
    `ConfirmDialog`, `Alert`, `Spinner`, `EmptyState`, `Breadcrumbs`, `Tabs`.
- Ícones inline em `src/components/ui/icons/` (`Plus`, `Trash`, `Edit`,
  `ChevronRight`, `Menu`, `Cpu`, `Layers`, `Building`, `Search`, etc.).

### 4. Camada de dados (`src/services/`)

- `api.ts`: `baseURL = '/api/v1'`; mantém `getErrorMessage`; **remove** o
  interceptor de resposta que limpa sessão e redireciona para `/login`.
- `tenant.ts`: mantém `create`, `list`; adiciona `get`, `update`, `remove`.
  `list` aceita paginação opcional (`skip`, `limit`).
- `app.ts`: mantém `create`, `listByTenant`; adiciona `get`, `update`,
  `remove`. Tipos `ApplicationOutput`, `CreateApplicationInput`,
  `UpdateApplicationInput`.
- `device.ts` (novo): `listByApp(appId)`, `create(payload)`, `remove(id)`.
  Tipos `DeviceOutput`, `CreateDeviceInput`.
- `auth.ts`: **removido**.
- Hook `src/hooks/useAsyncData.ts`: encapsula `loading`/`error`/`data`/`retry`
  para os fetches de página.

### 5. CRUD por entidade

| Entidade | Criar | Listar | Editar | Excluir |
| --- | --- | --- | --- | --- |
| Tenant | ✅ modal | ✅ lista de cards | ✅ modal | ✅ confirm |
| Application | ✅ modal (dentro do tenant) | ✅ lista | ✅ modal | ✅ confirm |
| Device | ✅ modal (dentro do app; app selecionável na visão global) | ✅ lista | ❌ | ✅ confirm |

- Validação `zod` espelhando o backend: nomes com mínimo de 2 caracteres;
  device com patterns hex (`^[0-9a-fA-F]{16}$` para `dev_eui`/`join_eui`,
  `^[0-9a-fA-F]{32}$` para `app_key`).
- Todas as mutações fazem refetch da lista afetada após sucesso.

### 6. Estados de UX

- Loading: `Spinner` central ou skeleton por página.
- Erro: `Alert` com mensagem (`getErrorMessage`) e botão "Tentar novamente".
- Vazio: `EmptyState` com CTA de criação.
- Exclusão: `ConfirmDialog` com nome do recurso e aviso irreversível.
- Sucesso de mutação: fecha modal e atualiza lista; feedback via `Alert`
  inline temporário no workspace.

### 7. Visão global de Devices

- Lista flat de todos os devices, resolvida varrendo `tenants → applications
  → devices`. Carregamento tolerante a falhas parciais
  (`Promise.allSettled`, igual ao `loadApplicationsByTenant` atual).
- Colunas: `dev_eui`, `join_eui`, application, tenant, criado em, ações.
- Criar device pela visão global exige escolher a application no modal
  (select aninhado tenant → app).
- Excluir direto na lista.

### 8. Testes e verificação

- Atualizar `src/mocks/handlers.ts`: adicionar handlers de `devices`
  (`GET /api/v1/devices`, `POST /api/v1/devices`, `DELETE
  /api/v1/devices/:id`) e alinhar handlers existentes de tenant/app ao
  contrato.
- Testes Vitest para: services (`tenant`, `app`, `device`), hook
  `useAsyncData` e utilitários de formatação.
- Gates obrigatórios (devem passar):
  - `npm run lint` (oxlint)
  - `npx tsc -b`
  - `npm run build`
  - `npm test` (vitest)

### 9. Mapa de arquivos

Novos:

- `src/components/ui/` — componentes do design system e `icons/`.
- `src/components/layout/AppShell.tsx`, `Sidebar.tsx`, `Topbar.tsx`.
- `src/hooks/useAsyncData.ts`.
- `src/services/device.ts`.
- `src/lib/format.ts` — datas e helpers de exibição.
- `src/pages/tenants/TenantListPage.tsx`,
  `src/pages/tenants/TenantDetailPage.tsx`.
- `src/pages/applications/ApplicationDetailPage.tsx`.
- `src/pages/devices/DeviceListPage.tsx` (global).

Modificados:

- `src/routes.tsx`, `src/App.tsx`, `src/main.tsx`, `src/index.css`,
  `tailwind.config.js`, `vite.config.ts`, `src/services/api.ts`,
  `src/services/tenant.ts`, `src/services/app.ts`, `src/mocks/handlers.ts`,
  `frontend/README.md`, `frontend/.env.example`.

Removidos:

- `src/pages/Login.tsx`, `src/services/auth.ts`, `src/pages/Dashboard.tsx`,
  `src/pages/AppDetail.tsx`, `src/pages/Devices.tsx`,
  `src/pages/Tenants.tsx`, `src/pages/app/NewApp.tsx`,
  `src/pages/tenants/NewTenant.tsx` (substituídos pelas novas páginas).
- `frontend/openapi-stub.yaml` permanece; ajustar apenas se divergir do
  contrato real.

### 10. Configuração de dev

- `vite.config.ts`: adicionar `server.proxy` para `/api` →
  `http://localhost:8000` (mesmo comportamento em produção via nginx).
- `.env.example`: remove `VITE_API_URL` absoluto (baseURL passa a ser
  relativo `/api/v1`); mantém `VITE_ENABLE_MOCKS`.

## Riscos e mitigação

- **N+1 na contagem de apps / devices globais.** Aceitável no volume atual.
  Mitigar com `Promise.allSettled` e tratamento de falha parcial; otimizar
  no backend depois (contadores/`include`).
- **Device create depende de ChirpStack configurado.** Se o backend retornar
  502/500, o `Alert` mostra a mensagem real (`getErrorMessage`). Não é bug do
  front.
- **Divergência de contrato.** `openapi-stub.yaml` pode estar desatualizado;
  a fonte de verdade é o `identity_api` (tabela do Contexto). Ajustar o stub
  se necessário.
- **Perda de trabalho ao remover páginas antigas.** São placeholders/baixo
  valor; histórico preservado no git.

## Critérios de sucesso

- Console navegável por drill-down Tenants → Applications → Devices, sem
  login, batendo no `identity_api` real via proxy `/api`.
- CRUD funcional de Tenant e Application (incluindo editar/excluir) e de
  Device (criar/listar/excluir), com estados de loading/erro/vazio em toda
  tela.
- Estética consistente e limpa (tema claro, design system, breadcrumbs,
  sidebar), alinhada à referência ThingsBoard.
- `npm run lint`, `npx tsc -b`, `npm run build` e `npm test` passam.
- Nenhuma dependência nova adicionada.
