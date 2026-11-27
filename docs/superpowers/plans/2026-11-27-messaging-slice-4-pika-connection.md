# Fatia 4 — Migração dos jobs para `pika.Connection`

**Issue:** #304
**ADRs/specs:** `docs/superpowers/specs/2026-11-27-pika-connection-adr.md`,
`docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`
**Roadmap:** `docs/superpowers/plans/2026-11-27-messaging-slices-2-6-roadmap.md`

## Objetivo

Implementar `linx_shared.messaging` e migrar publisher/consumer/topologia/health
do domínio de jobs para `pika.Connection` (Pika 1.5.0), removendo
`pika.BlockingConnection` do código de produção.

## Escopo

- `ports.py`: `Publisher` e `HealthProbe`.
- `pika_adapter.py`:
  - `open_channel(url)` para declaração/health one-shot;
  - `PikaPublisher` com confirmação (tag→future), `publish_raw` e detecção de
    retorno/nack;
  - `run_consumer` reescrito sobre `pika.Connection`, mantendo a política da
    Fatia 3.
- `connection_manager.py`: conexão com retry/backoff, `on_close_callback`,
  recuperação de canal e reconexão; separado da política de mensagens.
- Migrar `jobs_worker`, `jobs_status_worker`, health e `linx_shared/jobs`.
- Bump de `pika` para `1.5.0` nos locks.

## Fora do escopo

- Telemetria/`rabbitpy` (Fatia 5).
- Mudança de topologia/política (Fatias 2/3).

## Critérios de aceite

- Nenhum `pika.BlockingConnection` no código de produção.
- Contrato da outbox preservado: unroutable/nack não marcam publicado.
- Broker cai → worker reconecta e a outbox esvazia.
- Shutdown controlado sem thread residual.
- Suítes shared/jobs_worker/jobs_status_worker verdes, cobertura ≥ 70%,
  lint/mypy limpos.

## Riscos

- Mapeamento tag→future e retorno com `mandatory`; coberto pelo spike.
- Reconexão precisa de retry (o broker pode não aceitar imediatamente).
- Fakes de teste precisam simular confirmação/retorno.

## Plano de execução

1. ADR + `ports.py`.
2. `PikaPublisher` + testes.
3. `run_consumer` sobre `pika.Connection` + testes.
4. `open_channel` e migração de topologia/health/main.
5. Bump Pika e locks.
6. Suítes completas com Postgres e broker reais; remoção de Blocking.
