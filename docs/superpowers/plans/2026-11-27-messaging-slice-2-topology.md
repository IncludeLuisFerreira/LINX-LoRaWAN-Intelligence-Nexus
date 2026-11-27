# Fatia 2 — Topologia declarativa por tipo de job (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover a topologia fixa de `provisioning.application` e permitir que um segundo tipo de job publique `.requested`, `.started`, `.succeeded`, `.failed`, `.retry` e `.dead` sem `UnroutableError`.

**Architecture:** Um módulo puro (`linx_shared/messaging/topology.py`) descreve filas, DLQs e bindings por tipo. `broker.py` passa a declarar a topologia a partir dessa descrição, mantendo a fila legada `linx.jobs.provisioning` para `provisioning.application`. A fila de status única recebe uma binding `<tipo>.#` por tipo (sem catch-all).

**Tech Stack:** Python 3.12, Pika (declaração), pytest.

**Spec:** `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`
**Roadmap:** `docs/superpowers/plans/2026-11-27-messaging-slices-2-6-roadmap.md`

## Global Constraints

- Nenhum nome de fila/exchange/routing key hardcoded fora de `topology.py`/`constants.py`.
- `provisioning.application` mantém `linx.jobs.provisioning` e `linx.jobs.provisioning.dlq`.
- Tipos novos usam `linx.jobs.<tipo>` e `linx.jobs.<tipo>.dlq`.
- A fila de status é única (`linx.jobs.status`) e ganha uma binding por tipo.
- Sem binding catch-all `#`.
- Sem alterar a semântica da outbox nem a biblioteca de publicação nesta fatia.
- Cobertura ≥ 70%; `black`/`isort`/`flake8`/`mypy` limpos.

## Review Focus

1. **Tipo novo sem binding** → `UnroutableError` e outbox quarentenada. Teste de roteabilidade por tipo.
2. **Bindings duplicadas ou ausentes** → evento roteado para fila errada. Teste de conjunto de bindings.
3. **Regressão na fila legada** → jobs existentes param. Teste dos nomes legados.
4. **Override de `WORKER_QUEUE`** → fila customizada sem DLX/binding. Teste de fila customizada.
5. **Tipo duplicado no registro** → declaração ambígua. Teste de validação.

---

### Task 1: Módulo de topologia pura

**Files:**
- Create: `linx_core/shared/src/linx_shared/messaging/__init__.py`
- Create: `linx_core/shared/src/linx_shared/messaging/topology.py`
- Create: `linx_core/shared/tests/test_messaging_topology.py`

**Interfaces:**
- Produces:
  - `JobTypeTopology(job_type, command_queue, dead_letter_queue, requested_routing_key, dead_routing_key, status_binding)`
  - `job_type_topology(job_type: str, command_queue: str | None = None) -> JobTypeTopology`
  - `JOB_TYPE_TOPOLOGIES: tuple[JobTypeTopology, ...]`
  - `topologies_for(job_types: Sequence[str]) -> tuple[JobTypeTopology, ...]`

- [ ] **Step 1: Escrever os testes falhando**

Casos:
- `job_type_topology("provisioning.application")` usa os nomes legados.
- `job_type_topology("provisioning.tenant")` deriva `linx.jobs.provisioning.tenant`, `...dlq`, `provisioning.tenant.requested`, `.dead` e `. #`.
- `JOB_TYPE_TOPOLOGIES` contém exatamente `provisioning.application`.
- `topologies_for` rejeita lista vazia e tipo duplicado (`ValueError`).

- [ ] **Step 2: Rodar e ver falhar**

`poetry -C linx_core/shared run pytest tests/test_messaging_topology.py -q`

- [ ] **Step 3: Implementar**

`topology.py` com dataclass `frozen`, função de derivação e validação. Para o tipo legado, usar as constantes de `jobs/constants.py`.

- [ ] **Step 4: Rodar e ver passar**

---

### Task 2: `declare_topology` e `declare_status_topology` por tipo

**Files:**
- Modify: `linx_core/shared/src/linx_shared/jobs/broker.py:33-105`
- Modify: `linx_core/shared/tests/test_job_broker.py`

**Interfaces:**
- Consumes: `JobTypeTopology`, `JOB_TYPE_TOPOLOGIES`, `topologies_for`.
- Produces:
  - `declare_topology(channel, queue=PROVISIONING_QUEUE, job_types=None) -> None`
  - `declare_status_topology(channel, queue=PROVISIONING_STATUS_QUEUE, job_types=None) -> None`

- [ ] **Step 1: Atualizar testes**

- Default: exchanges, fila legada, DLQ legada, fila de status e bindings atuais continuam iguais.
- Dois tipos: fila/DLQ do segundo tipo + bindings `.requested`, `.dead`, `<tipo>.#`.
- `declare_status_topology` com dois tipos declara duas bindings.
- Fila customizada mantém DLX/binding da fila legada.

- [ ] **Step 2: Rodar e ver falhar**

- [ ] **Step 3: Implementar**

`declare_topology` itera `topologies_for(job_types or JOB_TYPE_TOPOLOGIES)`; aplica override de `queue` ao tipo legado; declara exchanges uma vez; declara fila de comando/DLQ e bindings por tipo; chama `declare_status_topology`.

`declare_status_topology` declara exchange de eventos + fila de status uma vez e uma binding `<tipo>.#` por tipo.

- [ ] **Step 4: Rodar e ver passar**

---

### Task 3: Prova de roteabilidade do segundo tipo

**Files:**
- Modify: `linx_core/shared/tests/test_job_broker.py`

**Interfaces:**
- Consumes: bindings produzidas por `declare_topology`.

- [ ] **Step 1: Escrever o teste**

Com `FakeChannel`, declarar dois tipos e provar que:
- `<tipo>.requested` casa com a binding da fila de comando;
- `<tipo>.started|succeeded|failed|retry` casam com `<tipo>.#` da fila de status;
- `<tipo>.dead` casa com a binding da DLX/DLQ.

Implementar um matcher de topic (`*`/`#`) no teste.

- [ ] **Step 2: Rodar e ver passar**

---

### Task 4: Suítes e qualidade

- [ ] `poetry -C linx_core/shared run pytest -q`
- [ ] `poetry -C linx_core/services/jobs_worker run pytest -q`
- [ ] `poetry -C linx_core/services/jobs_status_worker run pytest -q`
- [ ] `poetry -C linx_core/shared run black --check src tests`
- [ ] `poetry -C linx_core/shared run isort --check-only src tests`
- [ ] `poetry -C linx_core/shared run flake8 src tests`
- [ ] `poetry -C linx_core/shared run mypy src tests`

**Sem commit nesta fatia:** o usuário valida o diff antes.
