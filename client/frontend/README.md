# Frontend - React + TypeScript + Tailwind CSS

Dashboard web do ambiente isolado do cliente (`client/frontend/`). Console de
gestão da plataforma LINX. Permite administrar **Tenants**,
**Applications** e **Devices** consumindo o `identity_api` do `linx_core`.
Não há autenticação nesta versão — o acesso é direto.

## Stack

- **[Vite](https://vitejs.dev/)** — build tool e dev server.
- **[React 19](https://react.dev/)** + **TypeScript**.
- **[Tailwind CSS](https://tailwindcss.com/)** — design system com tokens de
  tema claro (fundo `slate-50`, superfícies brancas, acento azul).
- **[React Router](https://reactrouter.com/)** — roteamento SPA com `lazy`.
- **[Axios](https://axios-http.com/)** — cliente HTTP com `baseURL` `/api/v1`.
- **[Recharts](https://recharts.org/)** — gráfico de linha do dashboard de
  telemetria.
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
/dashboard                                   → menu de aplicações para escolher o dashboard
/dashboard/:appId                            → dashboard de telemetria (gráfico de linha)
/onboarding                                  → wizard de cadastro de device (3 passos; aceita `?app=<id>` para pré-selecionar a aplicação)
```

O dashboard é acessível pelo item **Dashboard** da sidebar (que abre o menu
de aplicações) ou pelo botão **Ver dashboard** na página da aplicação.

## Estrutura

```text
frontend/
├── public/
│   └── mockServiceWorker.js
├── src/
│   ├── components/
│   │   ├── QrScanner.tsx    # leitura de QR Code TR005 (câmera + manual)
│   │   ├── charts/          # TelemetryLineChart (Recharts)
│   │   ├── layout/          # AppShell, Sidebar, Topbar, PageHeader
│   │   └── ui/              # design system (Button, Card, Table, Modal, ...)
│   │       └── icons/       # ícones SVG inline
│   ├── hooks/
│   │   └── useAsyncData.ts  # loading/erro/reload para fetches de página
│   ├── mocks/               # handlers MSW (tenant, application, device)
│   ├── pages/
│   │   ├── tenants/         # TenantListPage, TenantDetailPage, TenantFormModal
│   │   ├── applications/    # ApplicationDetailPage, ApplicationFormModal
│   │   ├── devices/         # DeviceListPage, DeviceNicknameModal
│   │   ├── dashboard/       # DashboardSelectPage, Dashboard (telemetria)
│   │   ├── onboarding/      # OnboardingWizard (scan → confirm → select app)
│   │   └── NotFound.tsx
│   ├── services/            # api, tenant, app, device
│   ├── utils/               # cn, format, tr005 (parser do QR Code)
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
| Device | `GET /devices?app_id=`, `POST /devices`, `PATCH /devices/{id}`, `DELETE /devices/{id}` |
| Telemetry | `GET /telemetry?dev_eui=&limit=&before=` |

> O `PATCH /devices/{id}` aceita apenas `nickname`.

## Dashboard de Telemetria

A rota `/dashboard/:appId` busca o histórico via
`GET /telemetry?dev_eui=<dev_eui>&limit=100`, que responde
`{ items, next_cursor }`, onde cada item é
`{ time, dev_eui, payload, rssi, snr, app_id, event_type }`. O gráfico plota
uma métrica numérica do `payload` (o usuário escolhe entre as chaves numéricas
disponíveis) em função do tempo, com `recharts`.

O select de device mostra o **nickname** (com fallback para o `dev_eui`) e
oferece a opção **"Todos os devices"**, que busca o histórico de cada device e
sobrepõe as séries em um gráfico multi-linha (uma linha por device).

O componente se recarrega ao trocar de device ou de aplicação. Em
desenvolvimento sem backend, o MSW serve uma série sintética (`VITE_ENABLE_MOCKS=true`).

## Nickname de device

Cada device aceita um `nickname` opcional (até 50 caracteres), útil para
identificar o sensor. Ele é informado no **passo 2 do onboarding** e pode ser
editado depois pelo ícone de lápis nas tabelas de devices (lista global e
página da aplicação), que abre o `DeviceNicknameModal`. Quando vazio, a UI
exibe o `dev_eui` como fallback. A edição usa `PATCH /devices/{id}` e é
metadado local — não é enviada ao ChirpStack.

## Leitura de QR Code (TR005)

O cadastro de device aceita leitura de QR Code no padrão LoRa Alliance
TR005 (`LW:SchemaID:JoinEUI:DevEUI:ProfileID`, com extensões opcionais,
conforme TR005 §4.2/§4.3). O passo 1 do `OnboardingWizard` abre o
`QrScanner`, que lê pela câmera com `html5-qrcode` ou aceita o código
digitado manualmente. A decodificação preenche DevEUI e JoinEUI.

A AppKey **não** faz parte do QR TR005: ela é gerada localmente
(`generateAppKey()`) e o mesmo valor deve ser programado no dispositivo
antes do join (OTAA).

## Wizard de Onboarding

A rota `/onboarding` oferece o cadastro guiado em 3 passos (também
acessível pela barra lateral):

1. **Ler QR Code** — `QrScanner` (câmera ou colagem manual do TR005).
2. **Confirmar dados** — DevEUI, JoinEUI e AppKey pré-preenchidos e
   editáveis (validação com Zod), além de um nickname opcional; o ProfileID
   lido do QR é exibido.
3. **Selecionar App** — escolha da aplicação e do Device Profile. O
   wizard consulta `GET /device-profile/?app_id=` e, se o ProfileID do QR
   corresponder ao `id` ou `name` de um perfil, já o pré-seleciona (senão
   usa o primeiro).

O envio chama `POST /devices` com o contrato real (`dev_eui`, `join_eui`,
`app_key`, `app_id`, `device_profile_id`, `nickname`) e redireciona para
`/devices` em caso de sucesso.

A câmera exige *secure context* — funciona em `localhost` ou HTTPS, não
em HTTP via IP de LAN. Para testar sem QR físico, cole um código como:

```
LW:D0:1122334455667788:AABBCCDDEEFF0011:AABB1122
```

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
