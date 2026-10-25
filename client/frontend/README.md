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
- **[MSW (Mock Service Worker)](https://mswjs.io/)** — mocking de API e de
  WebSocket por contrato.
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

| Recurso     | Endpoints                                                                              |
| ----------- | -------------------------------------------------------------------------------------- |
| Tenant      | `POST/GET /tenant`, `GET/PATCH/DELETE /tenant/{id}`                                    |
| Application | `POST/GET /tenant/{tid}/applications`, `GET/PATCH/DELETE .../applications/{aid}`       |
| Device      | `GET /devices?app_id=`, `POST /devices`, `PATCH /devices/{id}`, `DELETE /devices/{id}` |
| Telemetry   | `GET /telemetry?dev_eui=&limit=&before=`                                               |

> O `PATCH /devices/{id}` aceita apenas `nickname`.

> **Contratos OpenAPI (#217):** há dois artefatos com papéis distintos:
> `client/frontend/openapi-stub.yaml` é o subconjunto REST que o front consome,
> validado por `@redocly/cli` no `frontend-ci`; `docs/openapi-stub.json` é o
> `app.openapi()` do `identity_api` materializado, mantido em sincronia por teste
> (`identity_api/tests/test_openapi.py`). O `yaml` orienta o front; o `json` é a
> fonte de verdade em runtime.

## Status de provisionamento

O componente `ProvisioningStatus` (`src/components/ProvisioningStatus.tsx`) é um
badge de apresentação puro para os estados `PENDING`, `PROVISIONING`, `RUNNING`
e `ERROR`, com os rótulos "Pendente", "Provisionando", "Em execução" e "Erro".
O estado `PROVISIONING` usa `animate-pulse`; todos os estados exibem o rótulo
textual, além da cor. O componente anuncia mudanças com `role="status"` e
`aria-live="polite"`.

O endpoint do backend ainda depende da issue #61 e o hook de polling
(`useProvisioningStatus`, issue #55) ainda não está integrado à tela. Com o MSW
habilitado (`VITE_ENABLE_MOCKS=true`), o handler simula a sequência
`PENDING -> PROVISIONING -> RUNNING`. Para forçar um estado no desenvolvimento,
defina no console do navegador:

```js
localStorage.setItem('linx:mock-provisioning-status', 'ERROR');
```

Recarregue a página para aplicar. Remova a chave para voltar à sequência:

```js
localStorage.removeItem('linx:mock-provisioning-status');
```

Sem MSW e sem o endpoint real, o hook de polling (issue #55) recebe 404 e o
badge permanece oculto.

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

### Tempo real (WebSocket)

O dashboard abre `WS /ws/telemetry/{app_id}` ao montar e aplica cada evento
recebido ao gráfico em ≤ 2s, sem refresh. A conexão é fechada no unmount ou na
troca de aplicação, e eventos de outro app/device são ignorados.

Em desenvolvimento, o dev server faz proxy de `/ws` para
`VITE_WS_PROXY_TARGET` e injeta `X-Service-Token: $DEV_SERVICE_TOKEN` no
handshake, porque o browser não consegue enviar headers em conexões WebSocket.
Com `VITE_ENABLE_MOCKS=true`, o MSW ativa um mock de WebSocket que emite
eventos a cada 2s.

### Fallback de polling (WebSocket offline)

Quando o WebSocket cai (`onclose`/`onerror`) ou fica preso em `connecting` por
mais de 5s sem `onopen`, o dashboard ativa um fallback REST: `useTelemetryPolling`
busca os itens mais recentes via `GET /telemetry?dev_eui=<dev_eui>&limit=50` a
cada 5s e os anexa ao gráfico pelo mesmo caminho do WebSocket (dedupe por
`(dev_eui, time, event_type)`). O `limit` é maior que 1 para não perder eventos
que chegam em rajada entre dois ticks; o dedupe descarta os já vistos.

O polling roda **indeterminadamente** enquanto o socket estiver `offline` — não
há reconexão de WebSocket nesta versão (issue #100). Quando a reconexão for
implementada, o status volta a `online` e o polling para sozinho.

Limitação de escopo: o fallback só cobre o **device selecionado**. No modo
**"Todos os devices"** o polling fica desativado, para não disparar N requisições
globais por tick.

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

A câmera exige _secure context_ — funciona em `localhost` ou HTTPS, não
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

O dev server faz **proxy de `/api` para `http://localhost:8000` e de `/ws` para
`VITE_WS_PROXY_TARGET`** (configurado em `vite.config.ts`), então não há CORS
envolvido. Ambos os proxies injetam
`X-Service-Token: $DEV_SERVICE_TOKEN`; defina `DEV_SERVICE_TOKEN` no `.env.local`
com o mesmo valor de `SERVICE_TOKEN` do backend, senão o `/api` responde `401` e
o `/ws` fecha com `4401`. Suba o `identity_api` no host em `http://localhost:8000`
para o `/api`. O `/ws` usa `VITE_WS_PROXY_TARGET`, que precisa apontar para um
`telemetry_consumer` alcançável a partir do host: publique ou encaminhe a porta
interna `8000` dele para outra porta local (por exemplo `8001`) e defina
`VITE_WS_PROXY_TARGET=http://localhost:8001` no `.env.local`. No Compose o
`telemetry_consumer` não publica porta no host.

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

| Variável               | Default                 | Descrição                                                                                                                          |
| ---------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `VITE_API_URL`         | `/api/v1`               | Base URL da API (relativo; resolvido pelo proxy).                                                                                  |
| `VITE_WS_URL`          | vazio                   | Base URL do WebSocket de telemetria. Vazio resolve para a mesma origem (`ws`/`wss`).                                               |
| `VITE_WS_PROXY_TARGET` | `http://localhost:8000` | Alvo do proxy `/ws` no dev server. Aponte para um `telemetry_consumer` alcançável (o default `localhost:8000` é o `identity_api`). |
| `DEV_SERVICE_TOKEN`    | vazio                   | Token injetado como `X-Service-Token` nos proxies `/api` e `/ws` do dev server. Obrigatório no dev.                                |
| `VITE_ENABLE_MOCKS`    | `false`                 | Liga o MSW no bundle. Use `true` para demos sem backend.                                                                           |

## Docker

Build multi-stage (Node → nginx). O `nginx.conf` faz fallback do SPA e proxy
de `/api/` para `BACKEND_URL` e de `/ws/` para `WS_BACKEND_URL`.

```bash
docker build -t frontend:dev .
docker run --rm -p 8080:80 \
  -e BACKEND_URL=http://host.docker.internal:8000 \
  -e WS_BACKEND_URL=http://host.docker.internal:8000 \
  -e SERVICE_TOKEN=dev-service-token \
  frontend:dev
```

Para habilitar mocks em um container de demonstração:

```bash
docker build --build-arg VITE_ENABLE_MOCKS=true -t frontend:demo .
```
