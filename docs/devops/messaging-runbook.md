# Runbook — Mensageria

Operação do broker único e dos fluxos de jobs/telemetria. Complementa o
design `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`.

## 1. Saúde

Telemetria (HTTP `/health` do `telemetry_consumer`):

```bash
curl -fsS -H "X-Service-Token: $SERVICE_TOKEN" \
  http://localhost:8011/health | jq
```

Campos úteis: `rabbitmq_connected`, `processed`, `failed`, `dead_lettered`,
`reconnects`, `last_error`.

Jobs: health dos containers (`docker compose ps`) e logs:

```bash
docker compose -f linx_core/docker-compose.yml logs -f jobs_worker jobs_status_worker
```

Broker:

```bash
docker compose -f infra/docker-compose.base.yml ps rabbitmq
docker compose -f infra/docker-compose.base.yml exec rabbitmq \
  rabbitmq-diagnostics -q ping
```

## 2. Filas e DLQs

Filas de jobs:

- `linx.jobs.provisioning` / `linx.jobs.provisioning.dlq`
- `linx.jobs.status` / `linx.jobs.status.dlq`
- uma fila/DLQ por tipo novo: `linx.jobs.<tipo>` / `linx.jobs.<tipo>.dlq`

Telemetria (por tenant):

- `linx.telemetry.<app_id>` / `linx.telemetry.<app_id>.dlq`
- auditoria: `linx.telemetry.audit`

Inspeção rápida:

```bash
docker compose -f infra/docker-compose.base.yml exec rabbitmq \
  rabbitmqctl list_queues name messages_ready messages_unacknowledged
```

Management UI (loopback): `http://127.0.0.1:15672`.

## 3. DLQ — diagnóstico e replay

1. Identifique a fila e a mensagem no management UI (ou `rabbitmqctl`).
2. Confirme o motivo no log:

```bash
docker compose -f linx_core/docker-compose.yml logs --tail=200 jobs_worker
# telemetria:
docker compose -f client/docker-compose.yml logs --tail=200 telemetry_consumer
```

3. Corrija a causa (payload, schema, credencial, dependência).
4. Replay:
   - **Jobs:** publique de volta na exchange `linx.jobs` com a routing key
     `<tipo>.requested` (ou use “Move messages” no management UI).
   - **Telemetria:** publique de volta na exchange `linx.telemetry.<app_id>` com
     a routing key original.
5. Consumidores são idempotentes (status de jobs e `ON CONFLICT` da telemetria);
   duplicatas são seguras, mas monitore `failed`/`dead_lettered`.

## 4. Outbox quarentenada

```sql
SELECT id, job_id, exchange, routing_key, attempts, last_error, failed_at
FROM job_outbox
WHERE failed_at IS NOT NULL
ORDER BY failed_at DESC;
```

Comando quarentenado marca o job `FAILED` com
`error.code=command_publish_failed`. Para reprocessar:

1. Corrija o broker/publicação.
2. Reenfileire a linha:

```sql
UPDATE job_outbox
SET failed_at = NULL, attempts = 0, next_attempt_at = now()
WHERE id = '<outbox_id>';
```

3. Se o job já foi marcado `FAILED`, recrie-o pela API (o comando original não
   será republicado sozinho).

## 5. Reconexão

- O consumer reconecta com backoff; `reconnects` no health indica a frequência.
- Se o broker caiu: verifique `rabbitmq-diagnostics`, logs e espaço em disco;
  suba o broker; os consumers redeclaram a topologia e retomam.
- Reconexões frequentes: verifique rede, heartbeat, memória do broker e
  `work_queue_maxsize` (consumers lentos).

## 6. Rotação de credencial

1. Atualize `RABBITMQ_ADMIN_*` em `infra/.env`, `linx_core/.env` e `client/.env`
   (valores iguais).
2. Reinicie broker e serviços.
3. Credenciais de tenant são provisionadas pela `identity_api` na criação da
   aplicação; para rotação, recrie a aplicação ou use a management API.

## 7. Alertas mínimos

- DLQ com mensagens crescendo.
- `dead_lettered`/`reconnects` aumentando no health da telemetria.
- Outbox com `failed_at` preenchido.
- Broker indisponível ou disco acima de 80%.

## 8. Lacunas de produto (issues)

- HA do broker: #312.
- Convergência do broker k8s: #313.
- Métricas Prometheus de mensageria: #314.
- TLS/AMQP seguro: #78.
- DR/backup: #128.
