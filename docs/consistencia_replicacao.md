# Consistência e Replicação de Dados (Entrega 3)

Este documento registra o modelo de consistência adotado no LINX e como a
replicação de dados é demonstrada na Entrega 3.

## Topologia

| Componente | Papel | Endereço interno |
| --- | --- | --- |
| `postgres-0` | primary (leitura e escrita) | `postgres-0.postgres.linx.svc.cluster.local:5432` |
| `postgres-1` | réplica (somente leitura) | `postgres-1.postgres.linx.svc.cluster.local:5432` |
| Service `postgres` | headless, endereça os pods individualmente | `postgres.linx.svc.cluster.local` |

O `DATABASE_URL` dos serviços aponta **sempre** para `postgres-0`. O Service
headless `postgres` resolve para os IPs das duas instâncias e não deve ser usado
para escrita.

## Modelo adotado

- **Replicação:** streaming replication assíncrona via WAL
  (`wal_level=replica`, `hot_standby=on`). A réplica aplica o WAL em tempo real,
  mas pode ficar alguns milissegundos atrás do primary.
- **Consistência na réplica:** **eventual**. Leituras na réplica podem observar
  dados defasados; são aceitáveis apenas onde o atraso não muda a decisão.
- **Escrita e read-after-write:** **no primary**. O `linx_shared` ainda expõe um
  único engine apontando para `postgres-0`; não há roteamento automático de
  leitura para a réplica nesta entrega.
- **Idempotência na ingestão:** o `telemetry_consumer` grava com
  `ON CONFLICT (app_id, dev_eui, time, event_type) DO NOTHING`. Reentrega da
  mesma mensagem não duplica o dado.
- **Ordenação do outbox:** o relay processa por
  `next_attempt_at, created_at`, preservando a ordem de tentativa dos jobs.
- **Exclusão mútua:** migrations usam `pg_try_advisory_lock(927351)`; jobs usam
  `FOR UPDATE SKIP LOCKED` + `locked_until`. Ambos permanecem no primary.

## Falhas e limitações

- **Sem failover automático.** Se `postgres-0` cair, `postgres-1` não é
  promovida automaticamente. A promoção é manual e está fora do escopo desta
  entrega.
- **Sem read/write split no código.** A issue #259 prevê `reader_engine` e um
  dependency `get_read_db()`, mas nesta entrega a réplica é usada para
  demonstração e consultas diretas.
- **Sem benchmark de lag automatizado.** A medição é feita ao vivo com
  `pg_stat_replication` e `pg_last_xact_replay_timestamp()`.
- **Relógios lógicos (Lamport) e lock em Redis** são a issue #258 e não fazem
  parte desta entrega. A ordenação atual usa timestamps do gateway/Postgres e a
  ordem do outbox.
- **Detalhes de `pg_stat_replication`/`pg_stat_wal_receiver`** (client_addr,
  replay_lag) exigem `pg_monitor` ou superusuário. O usuário `linxadm` vê a
  conexão e os LSNs; a prova de sincronização usa a comparação de LSN.

## Evidências

```bash
# papéis
kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" -c "SELECT pg_is_in_recovery();"'
# f = primary

kubectl -n linx exec postgres-1 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" -c "SELECT pg_is_in_recovery();"'
# t = replica

# conexão de streaming (uma linha: replicator | walreceiver)
kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "SELECT usename, application_name FROM pg_stat_replication;"'

# escrita no primary e leitura na réplica
kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "CREATE TABLE IF NOT EXISTS demo_replication (id uuid PRIMARY KEY, criado_em timestamptz DEFAULT now());
       INSERT INTO demo_replication (id) VALUES (gen_random_uuid());"'

kubectl -n linx exec postgres-1 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "SELECT count(*) FROM demo_replication;"'

# LSN do primary x reproduzido na réplica: podem divergir por ms; repita
# até o replay alcançar o valor do primary
PRIMARY_LSN=$(kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -Atc "SELECT pg_current_wal_lsn();"')

until [ "$(kubectl -n linx exec postgres-1 -- sh -c \
  "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" psql -U \"\$POSTGRESQL_USERNAME\" -d \"\$POSTGRESQL_DATABASE\" \
   -Atc \"SELECT pg_wal_lsn_diff(pg_last_wal_replay_lsn(), '$PRIMARY_LSN') >= 0;\"")" = "t" ]; do
  sleep 1
done

kubectl -n linx exec postgres-1 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -Atc "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();"'
```

Referências de código:

- `infra/kubernetes/base/postgres.yaml` — StatefulSet primary/replica.
- `linx_core/shared/src/linx_shared/db/base.py` — engine único no primary.
- `client/services/telemetry_consumer/src/telemetry_consumer/db.py` — upsert
  idempotente.
- `linx_core/shared/src/linx_shared/jobs/outbox.py` — ordenação do outbox.
- `linx_core/shared/src/linx_shared/db/migration_lock.py` — advisory lock.
