# Plataforma de Jobs Assíncronos — Design

**Data:** 2026-10-24
**Status:** Aprovado para planejamento

## Objetivo

Transformar o provisionamento Docker do `identity_api` em um fluxo assíncrono
durável, usando RabbitMQ e um worker genérico de jobs, sem acoplar o modelo de
dados ao provisionamento Docker.

## Decisões

- RabbitMQ é o broker. Não existe serviço que encapsula o broker.
- O roteamento é feito por exchange `topic` e bindings. Não existe worker
  central que re-roteia mensagens.
- Existe um worker genérico (`jobs_worker`) com registry de handlers por tipo
  de job. O handler de provisionamento é um adapter para o
  `docker_provisioner` via gRPC.
- O retorno do processamento é assíncrono via eventos no RabbitMQ.
- Um `jobs_status_worker` consome eventos e atualiza a tabela `jobs`.
- O contrato HTTP atual de provisionamento é substituído por `202 Accepted` +
  endpoint de consulta de job.
- O `docker_provisioner` e o contrato gRPC permanecem inalterados.
- Retry: até 3 tentativas para falhas transitórias, com backoff de 5s, 30s e
  2min.
- Uma operação ativa por `deduplication_key`; POSTs duplicados retornam o mesmo
  job.

## Não-objetivos

- Banco de dados separado por serviço.
- Workflow engine, DAGs ou orquestração multi-etapa.
- Exactly-once. O sistema é at-least-once e idempotente.
- Fila por tenant.
- Abstração multi-broker.
- Migrar o `docker_provisioner` para consumidor AMQP nativo nesta fase.

## Arquitetura

```text
cliente
  → identity_api
      → Postgres: jobs + job_outbox (mesma transação)
      → 202 Accepted

jobs_worker
  → job_outbox: relay publica em linx.jobs
  → consome linx.jobs.provisioning
  → registry: provisioning.application
  → ProvisioningAdapter
      → docker_provisioner gRPC :50052
  → grava evento de status em job_outbox
  → relay publica em linx.jobs.events

jobs_status_worker
  → consome linx.jobs.status
  → atualiza jobs no Postgres

cliente
  → GET /api/v1/tenant/{tenant_id}/jobs/{job_id}
```

O `identity_api` não acessa RabbitMQ. Ele só grava `jobs` e `job_outbox`. Se o
broker estiver indisponível, o POST continua retornando `202` e o outbox é
publicado quando o worker voltar.

## Contrato HTTP

### Criar job de provisionamento

```text
POST /api/v1/tenant/{tenant_id}/applications/{application_id}/provision
Header: X-Service-Token: <SERVICE_TOKEN>
```

Resposta `202 Accepted`:

```json
{
  "job_id": "uuid",
  "application_id": "uuid",
  "status": "pending",
  "created_at": "2026-10-24T12:00:00Z"
}
```

Header `Location`:

```text
/api/v1/tenant/{tenant_id}/jobs/{job_id}
```

Regras:

- `401` sem token válido.
- `404` tenant inexistente, application inexistente ou de outro tenant.
- `202` com o mesmo `job_id` se já existe job `pending` ou `running` para a
  application.
- Job concluído não bloqueia um novo POST; um novo job é criado.

### Consultar job

```text
GET /api/v1/tenant/{tenant_id}/jobs/{job_id}
```

Resposta `200`:

```json
{
  "job_id": "uuid",
  "type": "provisioning.application",
  "tenant_id": "uuid",
  "subject_id": "uuid",
  "status": "succeeded",
  "attempts": 1,
  "max_attempts": 3,
  "result": {
    "container_id": "abc",
    "port": 8421,
    "network": "linx-app-<app_id>",
    "image": "linx-tenant-app:latest",
    "status": "running",
    "created": true,
    "mqtt_topic": "application/<app_id>/device/+/event/up"
  },
  "error": null,
  "created_at": "2026-10-24T12:00:00Z",
  "started_at": "2026-10-24T12:00:01Z",
  "finished_at": "2026-10-24T12:00:02Z"
}
```

Estados: `pending`, `running`, `succeeded`, `failed`.

Erro de provisionamento não vira erro HTTP. Ele aparece em `error` com:

```json
{
  "code": "provisioner_unavailable",
  "message": "Provisioner error: ...",
  "retryable": true,
  "grpc_code": "UNAVAILABLE"
}
```

## Modelo de dados

### `jobs`

```text
id UUID PK
type TEXT NOT NULL
version INT NOT NULL DEFAULT 1
tenant_id UUID NOT NULL FK tenant ON DELETE CASCADE
subject_id UUID NOT NULL
status TEXT NOT NULL CHECK IN (pending,running,succeeded,failed)
attempts INT NOT NULL DEFAULT 0
max_attempts INT NOT NULL DEFAULT 3
payload JSONB NOT NULL
result JSONB NULL
error JSONB NULL
command_exchange TEXT NOT NULL
command_routing_key TEXT NOT NULL
deduplication_key TEXT NOT NULL
next_attempt_at TIMESTAMPTZ NULL
locked_until TIMESTAMPTZ NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
started_at TIMESTAMPTZ NULL
finished_at TIMESTAMPTZ NULL
```

Índices:

- único parcial `uq_jobs_active_dedup` em `deduplication_key` com
  `WHERE status IN ('pending','running')`.
- `ix_jobs_status_next_attempt` em `(status, next_attempt_at)`.
- `ix_jobs_tenant_created` em `(tenant_id, created_at DESC)`.
- `ix_jobs_subject` em `(subject_id)`.

### `job_outbox`

```text
id UUID PK
job_id UUID NOT NULL FK jobs ON DELETE CASCADE
exchange TEXT NOT NULL
routing_key TEXT NOT NULL
payload JSONB NOT NULL
published_at TIMESTAMPTZ NULL
attempts INT NOT NULL DEFAULT 0
next_attempt_at TIMESTAMPTZ NOT NULL
created_at TIMESTAMPTZ NOT NULL
```

Índice parcial `ix_job_outbox_pending` em `(published_at, next_attempt_at)`
com `WHERE published_at IS NULL`.

## Mensageria

### Envelope

```json
{
  "job_id": "uuid",
  "type": "provisioning.application",
  "version": 1,
  "tenant_id": "uuid",
  "subject_id": "uuid",
  "payload": {"application_id": "uuid"},
  "attempt": 0,
  "created_at": "2026-10-24T12:00:00Z",
  "trace_id": "uuid"
}
```

Propriedades AMQP:

- `delivery_mode=2`
- `content_type=application/json`
- `message_id=job_id`

### Topologia

```text
exchange linx.jobs (topic)
  binding provisioning.application.requested
    → queue linx.jobs.provisioning

exchange linx.jobs.dlx (direct)
  binding provisioning.application.dead
    → queue linx.jobs.provisioning.dlq

exchange linx.jobs.events (topic)
  binding provisioning.application.#
    → queue linx.jobs.status
```

### Eventos de status

Routing keys:

- `provisioning.application.started`
- `provisioning.application.succeeded`
- `provisioning.application.failed`
- `provisioning.application.retry`

Corpo:

```json
{
  "job_id": "uuid",
  "type": "provisioning.application",
  "status": "succeeded",
  "attempt": 1,
  "result": {},
  "error": null,
  "next_attempt_at": null,
  "finished_at": "2026-10-24T12:00:02Z"
}
```

O `jobs_status_worker` aplica transições idempotentes. Evento duplicado ou
atrasado não pode regredir um job terminal. Um evento `started` atrasado é
ignorado se `next_attempt_at` ainda está no futuro.

Toda saída do worker passa pelo outbox:

- comando inicial: exchange `linx.jobs`;
- eventos de status: exchange `linx.jobs.events`;
- retry: mesmo `command_exchange`/`command_routing_key` do job, com
  `next_attempt_at` no outbox;
- DLQ: exchange `linx.jobs.dlx`.

O worker de domínio não aplica `succeeded`/`failed`/`result` no job. Ele grava
o evento correspondente no outbox. O `jobs_status_worker` é o único escritor
do estado final.

## Worker de provisionamento

Fluxo por mensagem:

1. Valida o envelope.
2. Abre sessão e carrega o job com `FOR UPDATE`.
3. Se `succeeded` ou `failed`: ack e encerra.
4. Se `locked_until` no futuro: ack e encerra.
5. Se `next_attempt_at` está no futuro: ack e encerra.
6. Incrementa `attempts`, define `locked_until` e grava o evento `started` no
   `job_outbox`; commit.
7. Resolve o handler pelo `type`.
8. Executa o handler.
9. Sucesso: grava o evento `succeeded` no outbox, limpa `locked_until`; commit;
   ack.
10. Falha transitória com tentativa restante: grava o evento `retry` e um
    novo comando no outbox com `next_attempt_at = now + backoff`, limpa
    `locked_until`; commit; ack.
11. Falha permanente ou tentativas esgotadas: grava o evento `failed` e a
    mensagem da DLQ no outbox, limpa `locked_until`; commit; ack.

Classificação:

- Transitória: `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`.
- Permanente: `INVALID_ARGUMENT`, `FAILED_PRECONDITION`, `ABORTED`,
  `UNAUTHENTICATED`, `PERMISSION_DENIED`, `INTERNAL`, `UNKNOWN`.
- Exceção inesperada do handler: transitória com `code=handler_error`, até o
  limite.

O `ProvisionerClientError` precisa carregar `grpc_code` para essa classificação.

Handlers devem ser idempotentes. O worker pode reexecutar um handler após queda
entre a publicação do evento e o ack, ou após perda do ack. O provisioner já é
idempotente por label; os próximos handlers também precisam ser.

## Concorrência e recuperação

- `WORKER_CONCURRENCY` e `WORKER_PREFETCH` configuráveis.
- `pika` com uma conexão/canal por thread.
- Lease `JOB_LOCK_SECONDS=60`, maior que o timeout gRPC de 10s.
- Réplicas do worker competem na mesma fila.
- Mensagem não confirmada é reentregue pelo RabbitMQ.
- Job `running` com lease expirado é recuperado por um reaper periódico.
- O reaper libera o lease, grava o evento `retry` e um novo comando no outbox
  usando `command_exchange`/`command_routing_key` do job. O
  `jobs_status_worker` aplica `pending`.
- Ack sempre depois do commit no Postgres.

## Segurança

- Mensagens contêm apenas IDs, nunca `DB_PASSWORD`, tokens ou credenciais.
- `SERVICE_TOKEN` continua sendo usado apenas na chamada gRPC ao provisioner.
- `jobs_worker` não monta `/var/run/docker.sock`.
- Apenas `docker_provisioner` possui acesso ao socket Docker.
- Endpoint de status é escopado por `tenant_id`.

## Observabilidade

- Logs estruturados com `job_id`, `type`, `attempt`, `duration_ms`, `status`.
- Healthcheck do worker verifica Postgres e RabbitMQ.
- Métricas são evolução futura; não bloqueiam esta entrega.

## Testes

- Modelos e envelope: tabelas registradas, constraints, validação.
- API: 202, idempotência, 404, 401, status, isolamento por tenant.
- Outbox: publicação, retry de publicação, múltiplos workers com
  `SKIP LOCKED`.
- Worker: sucesso, transitório, permanente, tentativas esgotadas, lease,
  duplicata, mensagem atrasada.
- Status worker: idempotência e ordem.
- Migration: `upgrade head` e `downgrade -1`.
- OpenAPI stub atualizado.

## Rollout

1. Criar tabelas e migration.
2. Publicar `identity_api` com endpoint `202` e outbox.
3. Subir RabbitMQ e `jobs_worker`.
4. Validar provisionamento fim a fim.
5. Atualizar clientes para consultar o job.
6. Remover o caminho síncrono antigo e o cliente gRPC do `identity_api`.
