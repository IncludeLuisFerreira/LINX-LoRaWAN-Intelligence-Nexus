# Frontend - React + TypeScript + Tailwind CSS

Console de gestão da plataforma LINX. Permite administrar **Tenants**,
**Applications** e **Devices** consumindo o `identity_api` do `linx_core`.
Não há autenticação nesta versão — o acesso é direto.

## Stack

- **[Vite](https://vitejs.dev/)** — build tool e dev server.
- **[React 19](https://react.dev/)** + **TypeScript**.
- **[Tailwind CSS](https://tailwindcss.com/)** — design system com tokens de
  tema claro (fundo `slate-50`, superfícies brancas, acento azul).
- **[React Router](https://reactrouter.com/)** — roteamento SPA com `lazy`.
- **[Axios](https://axios-http.com/)** — cliente HTTP com `baseURL` `/api/v1`.
- **[React Hook Form](https://react-hook-form.com/) & [Zod](https://zod.dev/)** —
  formulários em modais com validação tipada.
- **[Vitest](https://vitest.dev/) + [Testing Library](https://testing-library.com/)**
  — testes de unidade e integração (cobertura mínima de 70%).
- **[MSW (Mock Service Worker)](https://mswjs.io/)** — mocking de API por
  contrato.
- **OxLint** / **Prettier** / **Husky** — qualidade e formatação.

## Navegação

Drill-down hierárquico com breadcrumbs:

```
/                                            → redireciona para /tenants
/tenants                                     → lista de tenants
/tenants/:tenantId                           → workspace (Applications | Configurações)
/tenants/:tenantId/applications/:appId       → workspace (Devices | Configurações)
/devices                                     → lista global de devices
```

## Estrutura

```text
frontend/
├── public/
│   └── mockServiceWorker.js
├── src/
│   ├── components/
│   │   ├── layout/          # AppShell, Sidebar, Topbar, PageHeader
│   │   └── ui/              # design system (Button, Card, Table, Modal, ...)
│   │       └── icons/       # ícones SVG inline
│   ├── hooks/
│   │   └── useAsyncData.ts  # loading/erro/reload para fetches de página
│   ├── mocks/               # handlers MSW (tenant, application, device)
│   ├── pages/
│   │   ├── tenants/         # TenantListPage, TenantDetailPage, TenantFormModal
│   │   ├── applications/    # ApplicationDetailPage, ApplicationFormModal, DeviceFormModal
│   │   ├── devices/         # DeviceListPage, DeviceCreateModal
│   │   └── NotFound.tsx
│   ├── services/            # api, tenant, app, device
│   ├── utils/               # cn, format
│   ├── routes.tsx
│   └── main.tsx
├── nginx.conf
├── vitest.config.ts
└── vite.config.ts
```

## API consumida

O front consome o `identity_api` via `baseURL` `/api/v1`:

| Recurso | Endpoints |
| --- | --- |
| Tenant | `POST/GET /tenant`, `GET/PATCH/DELETE /tenant/{id}` |
| Application | `POST/GET /tenant/{tid}/applications`, `GET/PATCH/DELETE .../applications/{aid}` |
| Device | `GET /devices?app_id=`, `POST /devices`, `DELETE /devices/{id}` |

> Device não possui edição (o backend não expõe `PATCH`).

## Desenvolvimento

```bash
cd frontend
npm install
npm run dev
```

O dev server faz **proxy de `/api` para `http://localhost:8000`**
(configurado em `vite.config.ts`), então não há CORS envolvido. Suba o
`identity_api` na porta 8000.

### Scripts

```bash
npm run dev          # dev server
npm run build        # typecheck + build de produção
npm run lint         # oxlint
npm run format       # prettier
npm test             # vitest (run)
npm run test:watch   # vitest (watch)
npx vitest run --coverage   # cobertura (mínimo 70%)
```

### Variáveis

| Variável | Default | Descrição |
| --- | --- | --- |
| `VITE_API_URL` | `/api/v1` | Base URL da API (relativo; resolvido pelo proxy). |
| `VITE_ENABLE_MOCKS` | `false` | Liga o MSW no bundle. Use `true` para demos sem backend. |

## Docker

Build multi-stage (Node → nginx). O `nginx.conf` faz fallback do SPA e proxy
de `/api/` para `BACKEND_URL`.

```bash
docker build -t frontend:dev .
docker run --rm -p 8080:80 \
  -e BACKEND_URL=http://host.docker.internal:8000 \
  frontend:dev
```

Para habilitar mocks em um container de demonstração:

```bash
docker build --build-arg VITE_ENABLE_MOCKS=true -t frontend:demo .
```
