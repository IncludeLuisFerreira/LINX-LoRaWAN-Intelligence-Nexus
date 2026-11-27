# Fatia 3 — Política de retry, DLQ e poison messages

**Issue:** #303 (absorve #234)
**Design:** `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`
**Roadmap:** `docs/superpowers/plans/2026-11-27-messaging-slices-2-6-roadmap.md`

## Objetivo

Uma política única de falha para mensagens internas: ACK no sucesso, retry
limitado em processo e DLQ confirmada ao esgotar. Mensagem inválida nunca é
descartada silenciosamente. Job com comando quarentenado na outbox chega a
estado terminal.

## Decisões

- **Poison** (`InvalidMessageError`): DLQ imediata, sem retry.
- **Erro transitório**: até `FailurePolicy.max_attempts` tentativas em
  processo, com delays `(1s, 2s)`; esgotado → DLQ.
- **DLQ confirmada**: publica no `linx.jobs.dlx` via `publish_raw` com
  publisher confirms; só então ACK. Se a publicação falhar, `nack(requeue=True)`.
- **Routing key da DLX**:
  - fila de status → `linx.jobs.status.dead` (DLQ `linx.jobs.status.dlq`);
  - fila de comando com envelope válido → `<tipo>.dead` (DLQ do tipo);
  - corpo inválido → `linx.jobs.status.dead`.
- **Fila de status** ganha DLX/DLQ. A mudança de argumentos exige recriar a
  fila em ambiente existente (MVP pré-lançamento).
- **#234**: quarentena de comando na outbox marca o job como `FAILED` com
  `error.code=command_publish_failed`, `finished_at` e limpa lease/retry.

## Fora do escopo

- Migração para `pika.Connection` (Fatia 4).
- Teto de retry da telemetria: a telemetria será migrada na Fatia 5; o cap
  acompanha a reescrita para não duplicar lógica no consumer antigo.

## Arquivos

- `linx_shared/messaging/policy.py` (novo)
- `linx_shared/jobs/consumer.py`
- `linx_shared/jobs/broker.py` (`publish_raw`, DLQ de status)
- `linx_shared/jobs/constants.py`
- `linx_shared/jobs/outbox.py`
- `jobs_status_worker/src/jobs_status_worker/main.py`
- testes em `shared`, `jobs_worker` e `jobs_status_worker`

## Critérios de aceite

- Payload inválido e retry esgotado terminam na DLQ correta.
- Mensagem de status inválida termina em `linx.jobs.status.dlq`, sem descarte.
- Job com comando quarentenado fica `FAILED` com `command_publish_failed`.
- Testes de unidade + integração de consumer/outbox; cobertura ≥ 70%.

## Validação executada

- `shared`: 191 passed, 1 skipped, cobertura 83.47%
- `jobs_worker`: 54 passed
- `jobs_status_worker`: 28 passed
- `black`, `isort`, `flake8`, `mypy`: limpos

Sem commit até validação humana.
