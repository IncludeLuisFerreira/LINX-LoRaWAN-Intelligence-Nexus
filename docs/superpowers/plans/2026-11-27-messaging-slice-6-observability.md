# Fatia 6 — Observabilidade, runbook e fechamento

**Issue:** #306
**Design:** `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`
**Roadmap:** `docs/superpowers/plans/2026-11-27-messaging-slices-2-6-roadmap.md`

## Objetivo

Tornar falhas de mensageria operáveis e fechar o épico: contadores no health,
runbook executável e issues dos itens de produto.

## Escopo

- `telemetry_consumer/health`: contadores `dead_lettered` e `reconnects`
  (já existiam `processed`, `failed`, `last_error`, `rabbitmq_connected`).
- Runbook `docs/devops/messaging-runbook.md` e entrada no `mkdocs.yml`.
- Quarentena de outbox: visível via log + SQL no runbook; contador dedicado
  fica na issue #314.
- Issues de produto: HA (#312), k8s (#313), métricas (#314). TLS (#78) e DR
  (#128) já existiam.
- Fechamento do épico após o merge das fatias.

## Fora do escopo

- Métricas Prometheus completas (#314).
- HA do broker (#312) e convergência k8s (#313).

## Critérios de aceite

- Health da telemetria expõe DLQ e reconexões.
- Runbook cobre DLQ, replay, outbox quarentenada, reconexão e rotação.
- Issues de produto criadas e linkadas.
- Testes/lint do telemetry_consumer verdes.

## Validação executada

- `telemetry_consumer`: 87 passed, 6 skipped
- `black`, `isort`, `flake8`, `mypy`: limpos
- Runbook adicionado ao nav do MkDocs
