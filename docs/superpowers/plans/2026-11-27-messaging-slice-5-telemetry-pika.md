# Fatia 5 — Telemetria no Pika, CI real e #254

**Issue:** #305 (absorve #254)
**Design:** `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`
**Roadmap:** `docs/superpowers/plans/2026-11-27-messaging-slices-2-6-roadmap.md`

## Objetivo

Remover `rabbitpy` do repositório e colocar `routing` e `telemetry_consumer`
sobre `pika.Connection`, mantendo o comportamento (retry, DLQ por tenant,
confirms, reconexão) e validando o pipeline no CI.

## Decisão de implementação

Para reduzir o risco de uma reescrita simultânea de dois serviços, foi criada
uma camada fina `pika_compat` que expõe o subconjunto da API já usada por
`routing`/`telemetry_consumer` sobre `pika.Connection`:

- `linx_shared.messaging.pika_compat` — usada pelo `routing`;
- cópia local em `telemetry_consumer/pika_compat.py` — o build Docker do
  consumer não inclui `linx_core/shared`, então não dá para importar o módulo
  compartilhado sem mudar o contexto de build.

A camada é transitória: a próxima evolução pode substituí-la diretamente por
`ports`/`pika_adapter`. O importante nesta fatia é não depender de `rabbitpy`.

## Escopo

- `routing`: `rabbitpy` → `pika_compat`/Pika; publisher confirms mantidos.
- `telemetry_consumer`: conexão/consumo/DLQ sobre Pika; handler/retry/DB/WS
  preservados.
- Remover `rabbitpy` de pyprojects e locks (routing, telemetry, integração).
- `tests/integration/conftest.py`: probe AMQP com `pika`.
- #254: job de CI `Isolation guard (dry-run + smoke)` no `integration-ci.yml`.
- Docs: remover menções funcionais ao `rabbitpy`.

## Fora do escopo

- Substituir a compat layer por `linx_shared.messaging.ports` no telemetry
  consumer (follow-up).
- Topologia declarativa de telemetria compartilhada: adiada para #316 (a Fatia 5
  preserva a topologia existente nos dois serviços).
- MQTT/Mosquitto.

## Critérios de aceite

- Nenhuma dependência/import `rabbitpy` no repositório.
- Integração real da telemetria verde (MQTT → routing → RabbitMQ →
  telemetry_consumer → REST/WS).
- Testes de isolamento multi-tenant executáveis no CI (sem skip).
- `ruff`/`black`/`isort`/`flake8`/`mypy` limpos; cobertura ≥ 70%.
- #254 coberto por job de CI.

## Validação executada

- `telemetry_consumer`: 87 passed, 6 skipped
- `routing`: 81 passed
- `tests/integration/run.sh`: 6 passed
- `scripts/test_isolation.py --dry-run`: OK
- `scripts/test_isolation_smoke.py`: 6 testes OK
- `grep rabbitpy`: nenhuma dependência/import (apenas docs históricas)
