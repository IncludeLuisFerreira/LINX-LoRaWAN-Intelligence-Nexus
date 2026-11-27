# Runbook — Mensageria

Operação do broker único e dos fluxos de jobs/telemetria. Complementa o
design `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`.

## 1. Saúde

Telemetria (`/health` dentro do container; a porta 8000 não é publicada no host):

```bash
docker compose -f client/docker-compose.yml exec -T telemetry_consumer \
  python - <<'PY'
import urllib.error
import urllib.request

try:
    print(urllib.request.urlopen("http://localhost:8000/health").read().decode())
except urllib.error.HTTPError as exc:
    print(exc.read().decode())
PY
```

Campos úteis: `rabbitmq_connected`, `processed`, `failed`, `dead_lettered`,
`reconnects`, `last_processed_at`. `last_error` não é exposto; use os logs.

Jobs: health dos containers e logs:

```bash
docker compose -f linx_core/docker-compose.yml ps
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
   - **DLQ de comando de job** (`linx.jobs.<tipo>.dlq`): publique na exchange
     `linx.jobs` com a routing key `<tipo>.requested`.
   - **DLQ de status** (`linx.jobs.status.dlq`): publique na exchange
     `linx.jobs.events` com a routing key original
     (`<tipo>.succeeded|failed|retry|started`); nunca use a exchange de
     comandos para um evento de status.
   - **Telemetria:** publique de volta na exchange `linx.telemetry.<app_id>` com
     a routing key original.
   - O management UI (“Move messages”) serve para os dois casos, desde que a
     exchange/routing key de destino esteja correta.
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
`error.code=command_publish_failed`. Recuperação:

1. Corrija o broker/publicação.
2. **Job já terminal (`FAILED`):** recrie o job pela API. Limpar `failed_at`
   sozinho não reabre um job terminal; o `claim_job` ignora jobs terminais.
3. **Linha de evento de status quarentenada:** reconcilie o job (o status
   terminal não foi aplicado) e alerte; não há replay automático.
4. Se precisar reaproveitar o payload, copie-o da linha da outbox e reenvie
   como um novo job — não altere o status do job antigo no banco.

## 5. Reconexão

- O consumer reconecta com backoff; `reconnects` no health indica a frequência.
- Se o broker caiu: verifique `rabbitmq-diagnostics`, logs e espaço em disco;
  suba o broker; os consumers redeclaram a topologia e retomam.
- Reconexões frequentes: verifique rede, heartbeat, memória do broker e os
  logs do consumer (consumer lento pode atrasar heartbeats).

## 6. Rotação de credencial

### 6.1 Credencial administrativa do broker

1. Troque a senha no broker (não basta editar `RABBITMQ_DEFAULT_PASS` e
   reiniciar com volume existente):

```bash
docker compose -f infra/docker-compose.base.yml exec rabbitmq \
  rabbitmqctl change_password "$RABBITMQ_ADMIN_USER" "<nova-senha>"
```

2. Atualize `RABBITMQ_ADMIN_PASSWORD` em `infra/.env` e `linx_core/.env`.
3. Reinicie o broker e os serviços que usam AMQP.
4. O `client/.env` não usa `RABBITMQ_ADMIN_*`; a telemetria usa `RABBIT_URL`
   (credencial do tenant).

### 6.2 Credencial de tenant (telemetria)

1. Re-provisione o usuário via management API
   (`PUT /api/users/tenant.{app_id}` com a senha derivada) ou recrie a
   aplicação pela `identity_api`.
2. Atualize `RABBIT_URL` em `client/.env` (URL-encode caracteres especiais) e
   reinicie o `telemetry_consumer`.
3. Se `RABBITMQ_TENANT_SECRET` for rotacionado, todas as senhas derivadas
   mudam; re-provisione todos os tenants.

## 7. Alertas mínimos

- DLQ com mensagens crescendo.
- `dead_lettered`/`reconnects` aumentando no health da telemetria. São
  contadores por processo: reiniciar o serviço zera os valores.
- Outbox com `failed_at` preenchido (consulta SQL da seção 4); o contador
  dedicado de quarentena fica na issue #314.
- Broker indisponível ou disco acima de 80%.

## 8. Lacunas de produto (issues)

- HA do broker: #312.
- Convergência do broker k8s: #313.
- Métricas Prometheus de mensageria: #314.
- TLS/AMQP seguro: #78.
- DR/backup: #128.
