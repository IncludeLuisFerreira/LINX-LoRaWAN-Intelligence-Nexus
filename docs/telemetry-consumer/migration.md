# Migração do banco — `telemetry_consumer`

Documento de migração para bancos TimescaleDB já existentes que rodavam o antigo
`tenant_app`. O `telemetry_consumer` grava na hypertable `telemetry` com as
colunas `app_id` e `event_type` e um índice único de deduplicação; bancos criados
antes dessa mudança precisam ser migrados **uma vez** antes de subir o serviço.

O novo esquema canônico está em `client/db/schema.sql` e
`deploy/db/schema.sql` (arquivos duplicados, mantidos
idênticos). Bancos novos já nascem migrados; o procedimento abaixo é apenas para
bancos existentes.

## Ordem de deploy

1. **Aplicar a migração** no TimescaleDB do tenant (SQL abaixo).
2. **Subir o `telemetry_consumer`** (`deploy/docker-compose.yml` ou
   `client/docker-compose.yml`).

A migração precisa vir antes do serviço: o `insert_event` usa
`ON CONFLICT (app_id, dev_eui, time, event_type)` e falha se o índice único não
existir. Mantenha a fila de auditoria `linx.telemetry.audit` do `routing` ativa
durante a transição para não perder telemetria.

## SQL de migração

O `time` está contido na chave única — requisito do TimescaleDB para índice único
em hypertable. O `app_id` entra na chave para não descartar eventos de
aplicações diferentes que compartilhem `dev_eui`, `time` e `event_type`.

```sql
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS app_id TEXT;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS event_type TEXT;
UPDATE telemetry SET event_type = 'up' WHERE event_type IS NULL;
ALTER TABLE telemetry ALTER COLUMN event_type SET NOT NULL;

-- Índice antigo (sem app_id), caso exista de uma migração anterior:
DROP INDEX IF EXISTS telemetry_dedup_idx;

-- Se já houver duplicatas (app_id, dev_eui, time, event_type), deduplicar antes:
DELETE FROM telemetry a USING telemetry b
 WHERE a.ctid < b.ctid
   AND a.app_id IS NOT DISTINCT FROM b.app_id
   AND a.dev_eui = b.dev_eui
   AND a.time = b.time
   AND a.event_type = b.event_type;

CREATE UNIQUE INDEX IF NOT EXISTS telemetry_dedup_idx
    ON telemetry (app_id, dev_eui, time, event_type);
```

Índice de leitura (idempotente, seguro repetir):

```sql
CREATE INDEX IF NOT EXISTS telemetry_dev_eui_time_idx
    ON telemetry (dev_eui, time DESC);
```

## Verificação

```sql
-- colunas esperadas
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'telemetry'
ORDER BY ordinal_position;

-- índices esperados
SELECT indexname FROM pg_indexes WHERE tablename = 'telemetry';

-- contagem de duplicatas restantes (deve ser 0)
SELECT app_id, dev_eui, time, event_type, count(*)
FROM telemetry
GROUP BY app_id, dev_eui, time, event_type
HAVING count(*) > 1;
```

## Reversão

A migração é aditiva (`app_id`, `event_type`, índice único). Reverter significa
remover as colunas e o índice — não recomendado, pois o `telemetry_consumer`
depende deles:

```sql
DROP INDEX IF EXISTS telemetry_dedup_idx;
ALTER TABLE telemetry DROP COLUMN IF EXISTS event_type;
ALTER TABLE telemetry DROP COLUMN IF EXISTS app_id;
```

> Referência completa do fluxo: `docs/superpowers/specs/2026-10-08-telemetry-consumer-design.md`.
