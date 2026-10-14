# Design: Dashboard em tempo real via WebSocket (issue #43)

Data: 2026-10-12
Status: aguardando revisão do spec

## Contexto

O dashboard fica em `client/frontend/` e atende a rota `/dashboard/:appId`. Hoje
ele busca o histórico com `GET /api/v1/telemetry?dev_eui=<dev_eui>&limit=100` e
plota o gráfico de linha (issue #42); o gráfico só muda quando o usuário troca o
device selecionado ou a página é recarregada.

O `telemetry_consumer` (`client/services/telemetry_consumer/`) já persiste cada
evento de telemetria no TimescaleDB e faz o fan-out do evento persistido para
todos os WebSockets conectados, na rota `WS /ws/telemetry/{app_id}` (issue #192).
O frontend ainda não consome esse stream.

Esta mudança conecta o dashboard ao WebSocket do `telemetry_consumer` e alimenta
o mesmo estado que o gráfico usa, para que cada novo evento apareça sem refresh.
Atende o RF-030 (telemetria em tempo real no dashboard) e o RNF-003 (latência
entre a chegada do pacote e a visualização ≤ 2s).

## Objetivo

- Abrir uma conexão `WS /ws/telemetry/{app_id}` ao montar o dashboard.
- Atualizar o gráfico em tempo real ao receber cada evento do stream.
- Fechar a conexão ao desmontar o componente ou trocar de aplicação.
- Aplicar cada evento somente quando ele pertence à aplicação e ao device
  selecionado.

## Não-objetivos

- Reconexão automática com backoff exponencial (issue #100).
- Fallback de polling em `GET /telemetry` a cada 5s quando o WebSocket cai
  (issue #44).
- Autenticação/autorização no WebSocket (documentado como pendência de hardening
  do `telemetry_consumer`, sem token neste escopo).
- Alterar o backend `telemetry_consumer`, `broadcaster` ou o contrato das rotas
  de leitura.
- Indicador visual de estado da conexão (conectado/desconectado).

## Decisões

- **Contrato da mensagem**: o corpo recebido no WebSocket é o mesmo registro
  retornado por `GET /telemetry`, ou seja um `TelemetryItem`:
  `{ time, app_id, dev_eui, event_type, payload, rssi, snr }`. O frontend valida
  a presença dos campos essenciais (`time`, `dev_eui`, `payload`) e ignora o
  evento se a validação falhar.
- **Resolução da URL**: `buildTelemetrySocketUrl(appId)` usa `VITE_WS_URL` como
  base quando definida; caso contrário deriva o esquema de `window.location`
  (`https:` → `wss:`, senão `ws:`) e usa `window.location.host`. O caminho é
  sempre `/ws/telemetry/{appId}`. Isso mantém same-origin em produção e permite
  apontar para outro host em dev.
- **Identidade do app**: `{app_id}` é o `appId` da rota (`/dashboard/:appId`),
  que é o UUID da aplicação e corresponde ao `APP_ID` do `telemetry_consumer`. O
  backend fecha a conexão com código `1008` quando não corresponde.
- **Sem reconexão**: a conexão é aberta uma vez por `appId`; se cair, o hook não
  tenta reconectar (fora de escopo). O gráfico continua exibindo o histórico já
  carregado.
- **Deduplicação**: um evento pode chegar pelo stream e já estar no histórico
  REST (ou chegar repetido). O frontend remove duplicatas por
  `(dev_eui, time, event_type)`, a mesma chave única do TimescaleDB.
- **Sem refetch no evento**: o evento do stream é anexado ao estado local; não
  dispara nova chamada REST.

## Arquitetura e componentes

### `client/frontend/src/services/telemetry.ts`

Duas funções puras, testáveis isoladamente:

- `buildTelemetrySocketUrl(appId: string): string` — resolve a URL conforme a
  decisão acima. Lê `import.meta.env.VITE_WS_URL` e `window.location`.
- `appendItem(items: TelemetryItem[], item: TelemetryItem): TelemetryItem[]` —
  retorna uma nova lista ordenada por `time` sem o item duplicado (chave
  `(dev_eui, time, event_type)`).

### `client/frontend/src/hooks/useTelemetrySocket.ts` (novo)

```ts
export function useTelemetrySocket(
  appId: string,
  onMessage: (item: TelemetryItem) => void,
): void
```

- `useEffect` com dependência `[appId]`: cria
  `new WebSocket(buildTelemetrySocketUrl(appId))`.
- `onmessage`: faz `JSON.parse`, valida o shape de `TelemetryItem` e chama
  `onMessage`; payload inválido é ignorado sem lançar.
- `onerror`/`onclose`: encerram sem lançar.
- Cleanup: `ws.close()`.
- O callback é mantido em um `ref` para que mudanças no handler não reabram o
  socket.
- É limpo sob o `React.StrictMode` (mount duplo em dev).

### `client/frontend/src/pages/dashboard/Dashboard.tsx`

- Novo estado `liveItems: TelemetryItem[]`, resetado quando `appId` muda.
- `useTelemetrySocket(appId, onMessage)`:
  - ignora o evento se `item.app_id !== appId`;
  - anexa via `appendItem` quando o device selecionado é "Todos os devices" ou
    quando `item.dev_eui === activeDevEui`.
- As séries do gráfico passam a ser derivadas da mesclagem entre o histórico
  REST (por device) e os `liveItems` correspondentes, com `appendItem`
  deduplicando. `metrics`, `activeMetric`, `lastReadingTime` e `chartSeries`
  continuam derivados desse conjunto combinado, então o `TelemetryLineChart`
  re-renderiza sozinho.

### Configuração de dev e build

- `client/frontend/vite.config.ts`: adicionar proxy `/ws` com `ws: true` (alvo
  configurável; o proxy só é usado quando `VITE_WS_URL` não está definida e o
  hook resolve same-origin).
- `client/frontend/nginx.conf`: adicionar `location /ws/` com
  `proxy_http_version 1.1` e os cabeçalhos `Upgrade`/`Connection`, encaminhando
  para `WS_BACKEND_URL` (novo env, independente de `BACKEND_URL`, usado pelo
  `/api/`).

### Mock de demonstração

- Novo `client/frontend/src/mocks/websocket.ts` usando `ws.link` do MSW 2, que
  emite um ponto sintético periódico em `*/ws/telemetry/:appId`, registrado no
  `mocks/browser.ts` apenas quando `VITE_ENABLE_MOCKS=true`. Arquivos de `mocks/`
  são excluídos da cobertura.

## Fluxo de dados

```
telemetry_consumer
  consome AMQP → persiste (insert idempotente) → broadcaster.broadcast(item)
        │
        ▼
WS /ws/telemetry/{app_id}  ──▶  useTelemetrySocket (frontend)
                                        │ valida + filtra app_id/device
                                        ▼
                              appendItem(liveItems, item)
                                        │
                                        ▼
                         histórico REST + liveItems → chartSeries
```

## Tratamento de erros

- **JSON inválido ou shape inesperado**: evento descartado, sem exceção.
- **`app_id` divergente**: o backend fecha com `1008`; o `onclose` apenas
  encerra. Sem feedback visual neste escopo.
- **Falha ao abrir / queda do socket**: `onerror`/`onclose` encerram; o gráfico
  mantém o histórico já carregado (sem polling).
- **Histórico REST falha**: comportamento atual preservado (erro com retry);
  o stream não interfere nessa tela.

## Estratégia de testes

Ferramenta: Vitest + Testing Library + MSW. Limite global de cobertura: 70%.

`client/frontend/src/services/telemetry.test.ts` (unit):
- `buildTelemetrySocketUrl` delega a `VITE_WS_URL` quando definida.
- Deriva `ws:` e `wss:` conforme `window.location.protocol`.
- Monta o caminho `/ws/telemetry/{appId}`.
- `appendItem` deduplica pela chave `(dev_eui, time, event_type)` e mantém a
  ordem por `time`.

`client/frontend/src/hooks/useTelemetrySocket.test.tsx` (unit, com uma classe
`FakeWebSocket` injetada em `globalThis.WebSocket`):
- Abre a URL correta para o `appId` (caminho feliz).
- `onmessage` válido chama o callback com o item parseado.
- JSON inválido e shape incompleto não chamam o callback e não lançam.
- `close` é chamado ao desmontar (critério de aceite).
- Trocar `appId` fecha a conexão antiga e abre uma nova.
- `onerror` não lança.

`client/frontend/src/pages/dashboard/Dashboard.test.tsx` (integração, com
`vi.mock` do hook `useTelemetrySocket`):
- Emitir um evento atualiza o gráfico e a "Última leitura" sem nova chamada REST
  (critério de aceite).
- Evento de outro `dev_eui` é ignorado quando um device específico está
  selecionado e aceito no modo "Todos os devices".
- Evento de outro `app_id` é ignorado.
- Sem device/métrica, o recebimento não quebra a tela.

## Documentação

- `client/frontend/README.md`: nova seção "Tempo real (WebSocket)" cobrindo a
  conexão, o fechamento no unmount, a variável `VITE_WS_URL` e o proxy `/ws` de
  dev.
- `client/README.md` (e o espelho `docs/client/README.md`): mencionar o consumo
  do stream no dashboard.

## Riscos e questões em aberto

1. **Roteamento de infra no deploy unificado.** `deploy/nginx/nginx.conf`
   encaminha tudo para `identity_api:8000` e o `telemetry_consumer` não publica
   porta (`deploy/docker-compose.yml`). Sem uma rota `/ws/` até o
   `telemetry_consumer`, o critério de aceite (publicar via MQTT e ver o ponto)
   não fecha fora do ambiente local. Definir se a rota entra nesta issue ou em
   uma issue de infra separada.
2. **Backend do WebSocket no compose do cliente.** Em `client/docker-compose.yml`
   não há `identity_api`; o alvo do WS (`WS_BACKEND_URL`) precisa ser definido
   (provavelmente o serviço `telemetry_consumer`).
3. **REST `/api/v1/telemetry`.** O `identity_api` não expõe rota de telemetria; o
   histórico REST do dashboard depende de um proxy até o `telemetry_consumer`
   (issue #42/#51), ainda indisponível. O tempo real não corrige esse caminho.
4. **`1008` sem feedback.** Um `app_id` divergente fecha a conexão silenciosamente;
   aceitável neste escopo, candidato a melhoria futura.
5. **Sem auth no WebSocket.** Mantido conforme o design do `telemetry_consumer`.

## Referências

- Issue #43 — `feat(frontend): connect dashboard to Client Agent WebSocket (real-time)`
- `docs/superpowers/specs/2026-10-08-telemetry-consumer-design.md` — `WS /ws/telemetry/{app_id}`
- `docs/superpowers/plans/2026-10-12-device-nickname-multiline-dashboard.md` — dashboard multi-linha (issue #42)
- `PRD_PLATAFORMA_IOT.md` — RF-030, RNF-003
