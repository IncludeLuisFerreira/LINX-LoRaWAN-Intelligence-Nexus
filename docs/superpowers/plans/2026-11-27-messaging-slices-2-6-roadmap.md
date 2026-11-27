# LINX Messaging — Roadmap das Fatias 2–6

**Épico:** consolidação da mensageria.
**Design:** `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`
**Fatia 1:** concluída (PR #301, issue #300) — broker único, integração com serviços reais, remoção do `deploy/`.

| Fatia | Escopo | Issue | Status |
|---|---|---|---|
| 0 | Spike Pika 1.5.0 (`pika.Connection`) | #302 | mergeada (PR #310) |
| 2 | Topologia declarativa por tipo | #233 | mergeada (PR #308) |
| 3 | Retry/DLQ/poison + outbox (#234) | #303 | mergeada (PR #309) |
| 4 | Migrar jobs para `pika.Connection` | #304 | mergeada (PR #310) |
| 5 | Telemetria no adaptador + CI real (#254) | #305 | PR #311 aberta |
| 6 | Observabilidade, runbook e fechamento | #306 | PR #315 aberta (empilhada na #311) |

Itens de produto criados: HA #312, convergência k8s #313, métricas #314.
TLS #78 e DR #128 já existiam. A quarentena de outbox fica observável por
log/SQL nesta entrega; o contador dedicado está no escopo de #314.

## Como este documento é usado

Este é um **roadmap**, não um plano task-by-task. Cada fatia ganha seu próprio
plano detalhado (`docs/superpowers/plans/YYYY-MM-DD-...md`) no início da
execução, com arquivos, assinaturas, testes e passos TDD. O plano detalhado
pode ajustar nomes e ordem, mas não o escopo nem os critérios de aceite aqui.

Regras comuns a todas as fatias:

- branch própria a partir de `develop` atualizado; PR com a issue da fatia;
- `pytest` para aplicação/integração; `unittest` só para ferramentas em `scripts/`
  (ver `scripts/tests/README.md`);
- cobertura mínima de 70% por pacote, mantendo os gates de CI;
- sem segredos reais em código/compose/docs;
- nada de `git add .`; commits em português com `(#N)`;
- escopo estrito: problema fora da fatia vira issue, não “aproveitamento”.

## Dependências

```
Fatia 0 (spike) ──────────────┐
                              ▼
Fatia 2 (#233) → Fatia 3 → Fatia 4 → Fatia 5 → Fatia 6
```

- **Fatia 0** pode começar em paralelo; é gate da Fatia 4.
- **Fatia 2** depende do merge da PR #301.
- **Fatia 3** depende da topologia declarativa da Fatia 2.
- **Fatia 4** depende do spike (0) e da política (3).
- **Fatia 5** depende do adaptador Pika da Fatia 4.
- **Fatia 6** fecha o épico depois das anteriores.

## Fatia 0 — Spike Pika 1.5.0 (`pika.Connection`)

**Issue:** #302
**Objetivo:** provar, com código descartável, que `pika.Connection` cobre o
contrato de mensageria antes de investir na migração.

Perguntas obrigatórias:

1. Publisher confirmado: mapear tag (`on_publish`) → future → ACK/NACK/return
   sem corrida, com timeout?
2. `mandatory=True` + `add_on_return_callback` detecta mensagem não roteada?
3. Consumo com ACK manual em thread de trabalho encerra limpo com `stop_event`?
4. `on_close_callback` permite recriar conexão, canais, topologia e consumidores
   sem vazar threads?
5. `basic_nack` + DLX leva a mensagem para a DLQ?
6. `work_queue_maxsize`/`shutdown_drain_timeout` se comportam sob consumer lento?

**Entrega:** ADR `docs/superpowers/specs/2026-11-27-pika-connection-adr.md` e um
exemplo executável. Nenhum código de produção é mergeado.
**Critério de saída:** decisão “segue com `pika.Connection`” ou fallback
registrado no ADR. Se o mapeamento de confirms não for confiável, a Fatia 4
para e a decisão volta para revisão.
**Demo:** rodar o exemplo contra um broker local: publicar, confirmar, forçar
unroutable, matar conexão e reconectar.

## Fatia 2 — Topologia declarativa (#233)

**Issue:** #233 (existente)
**Objetivo:** eliminar a topologia hardcoded de `provisioning.application` e
permitir um segundo tipo de job sem `UnroutableError`.

Escopo:

- `linx_shared/jobs/topology.py` (ou `linx_shared/messaging/topology.py`) com
  exchanges, filas, DLQs e bindings declarativos por tipo.
- Uma fila de comando e uma DLQ por tipo; a fila de status única ganha uma
  binding `<tipo>.#` por tipo (sem catch-all `#`).
- `declare_topology(channel, tipos)` idempotente; chamado no startup com o
  registro de tipos.
- Atualizar `constants.py`, `broker.py`, `jobs_worker/main.py`,
  `jobs_status_worker/main.py` e testes.
- Teste de roteabilidade de um segundo tipo sintético cobrindo `.requested`,
  `.started`, `.succeeded`, `.failed`, `.retry` e `.dead`.

**Fora do escopo:** política de retry/DLQ (Fatia 3), migração de biblioteca
(Fatia 4), schema da outbox.
**Depende de:** PR #301 mergeada.
**Demo:** publicar os eventos do segundo tipo e mostrar filas/bindings no
management UI, sem erro no publisher.
**Risco:** a fila de status existente pode precisar de DLX; se o argumento
mudar, recriar a fila é aceitável (MVP pré-lançamento, decisão no design).

## Fatia 3 — Política de retry, DLQ e poison messages (#234)

**Issue:** #303 (absorve #234 como sub-item)
**Objetivo:** uma política única de falha, sem descarte silencioso nem requeue
infinito.

Escopo:

- `linx_shared/messaging/policy.py` (ou `jobs/policy.py`) com decisão
  `ACK` / `RETRY` / `DLQ`.
- Mensagem inválida/venenosa → DLQ **sempre**.
- Retry de infraestrutura limitado e com backoff em processo; esgotado → DLQ.
- DLQ por publicação confirmada no DLX, depois ACK (at-least-once).
- Fila de status ganha DLX/DLQ.
- #234: quarentena de comando na outbox grava `FAILED` com
  `error.code=command_publish_failed`; quarentena de evento dispara
  reconciliação/alerta; job não fica `PENDING`/`RUNNING` para sempre.
- Teto curto para o retry em processo da telemetria.

**Fora do escopo:** migrar para `pika.Connection` (Fatia 4).
**Depende de:** Fatia 2.
**Demo:** injetar payload inválido e retry esgotado; mostrar DLQ e job terminal
via API.
**Testes:** unidade da política; integração com broker real para DLQ e
quarentena.

## Fatia 4 — Migração dos jobs para `pika.Connection`

**Issue:** #304
**Objetivo:** implementar `linx_shared.messaging` e migrar o domínio de jobs
para a API nova, removendo `pika.BlockingConnection` do código de produção.

Escopo:

- `ports.py`: `Publisher`, `Consumer`, `TopologyBuilder`, `HealthProbe`.
- `pika_adapter.py`: implementação sobre `pika.Connection` (1.5.0), com
  publisher confirmado (tag → future), ACK/NACK e DLQ.
- `connection_manager.py`: reconexão com backoff, recovery de canais,
  redeclaração de topologia e recriação de consumidores.
- Migrar `jobs_worker`, `jobs_status_worker`, health e `linx_shared/jobs`.
- Bump `pika` para `1.5.0` nos `pyproject.toml`/locks.
- Testes de reconexão, shutdown e confirmação.

**Fora do escopo:** telemetria (`rabbitpy` permanece até a Fatia 5).
**Depende de:** Fatia 0 (gate) e Fatia 3.
**Demo:** derrubar o broker, publicar um job e ver o worker reconectar e a
outbox esvaziar sem perda.
**Risco:** semântica fire-and-forget do `basic_publish`; o adaptador precisa
reconstruir o contrato de erro da outbox. O ADR do spike é obrigatório.

## Fatia 5 — Telemetria na topologia comum, CI com broker real e #254

**Issue:** #305 (absorve #254)
**Objetivo:** remover `rabbitpy`, colocar `routing`/`telemetry_consumer` no
adaptador Pika e garantir integração real no CI.

Escopo:

- Migrar `middleware/services/routing` e `client/services/telemetry_consumer`
  para `linx_shared.messaging`.
- Topologia de telemetria declarativa (exchange/fila/DLQ por tenant).
- Remover `rabbitpy` dos pyprojects/locks.
- CI: broker de verdade nos jobs de integração; #254 (script de isolamento no
  CI) incluído.
- Testes de isolamento multi-tenant sem skip.

**Fora do escopo:** MQTT/Mosquitto (#81/#105/#108/#110/#112/#125/#255).
**Depende de:** Fatia 4.
**Demo:** pipeline MQTT → routing → RabbitMQ → consumer → REST/WS verde no CI,
com teste de isolamento entre dois tenants.

## Fatia 6 — Observabilidade, runbook e fechamento

**Issue:** #306
**Objetivo:** tornar falhas operáveis e encerrar o épico.

Escopo:

- Contadores de DLQ, reconexões e quarentena expostos no health/log.
- Alertas mínimos documentados (sem Prometheus nesta entrega).
- Runbook: DLQ, replay, quarentena, reconexão e rotação de credencial.
- Atualizar design/READMEs; fechar issues das fatias.
- Criar issues dos itens de produto (HA do broker, TLS, métricas, DR, k8s).

**Depende de:** Fatias 3, 4 e 5.
**Demo:** health com contadores, simulação de DLQ e runbook executável.

## Definition of Done (todas as fatias)

- Testes e gates de CI verdes; cobertura ≥ 70% no pacote tocado.
- `black`, `isort`, `flake8`, `mypy` limpos.
- Sem `BlockingConnection`/`rabbitpy` onde a fatia já migrou.
- Docs vivas atualizadas; sem referência a caminho removido.
- PR com a issue vinculada e demo descrita.
- Problemas fora do escopo reportados como issue, não corrigidos “de passagem”.
