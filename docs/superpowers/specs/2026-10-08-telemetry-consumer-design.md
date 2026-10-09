# Consumidor RabbitMQ `linx.telemetry` → TimescaleDB (tenant)

- **Data:** 2026-10-08
- **Status:** Proposto
- **Escopo:** Novo microserviço `client/services/telemetry_consumer`, que consome o
  exchange `topic` durável `linx.telemetry` do RabbitMQ, persiste os eventos na
  hypertable `telemetry` do TimescaleDB do tenant e expõe os caminhos de leitura
  (`GET /telemetry` e WebSocket) ao frontend. Remove o `tenant_app` e o
  encaminhamento REST `/ingest` do `client_agent`, tornando o RabbitMQ o único
  caminho de ingestão.

## Contexto

A PR #191 transformou `middleware/services/routing` em serviço de ingestão: ele
consome uplinks do ChirpStack via MQTT, valida a integridade, normaliza um
envelope e publica no exchange `topic` durável `linx.telemetry`. O `routing` já
declara a fila de auditoria `linx.telemetry.audit` (binding `#`), mas **não existe
consumidor** que persista o dado.

O caminho atual de persistência é o `POST /ingest` do `tenant_app`
(`client/src/tenant`), alimentado por encaminhamento REST do `client_agent`
(`TENANT_APP_URL`). Esse desenho acopla o middleware ao destino e mantém um hop
HTTP que o RabbitMQ já supera. A entrega do `routing` é **at-least-once**: o ack
MQTT só ocorre após o confirm do RabbitMQ, então uma republicação por
timeout/nack pode duplicar. O consumidor precisa ser idempotente.

O `tenant_app` deixa de ter uso: ingestão passa a ser AMQP, e leitura
(`GET /telemetry`, WebSocket) migra para o consumidor, que já detém o pool do
banco e recebe os eventos em processo.

## Objetivos

1. Declarar, por aplicação, uma fila durável `linx.telemetry.{app_id}` com
   binding `application.{app_id}.#` (fan-out por tenant) e consumir via AMQP.
2. Mapear o envelope (`app_id`, `dev_eui`, `event_type`, `payload`, `rssi`,
   `snr`, `timestamp`) para a hypertable `telemetry` do TimescaleDB.
3. Ser **idempotente** frente a redelivery de mensagem duplicada.
4. Tratar falha de processamento sem perder o dado (retry + DLQ por tenant).
5. Expor leitura ao frontend: `GET /telemetry` (histórico) e
   `WS /ws/telemetry/{app_id}` (tempo real).
6. Remover `tenant_app` e o encaminhamento REST `/ingest` do `client_agent`.

## Não-objetivos

- Autenticação/autorização nos endpoints de leitura e no WebSocket (TLS/auth de
  frontend continua para as issues de hardening).
- Deduplicação por `f_cnt`/contador LoRaWAN. A idempotência usa a chave do
  envelope (`dev_eui`, `time`, `event_type`).
- Alterar o `routing`, o publisher ou a fila de auditoria.
- Remover a tabela `device_routes` do plano de controle (issue de limpeza à
  parte).
- Reescrever o `routing` ou qualquer serviço em asyncio.

## Arquitetura

Um único microserviço por tenant, dono do pool do TimescaleDB e da fila do
tenant. O consumer roda em thread dedicada (rabbitpy é bloqueante) e delega a
persistência ao event loop (asyncpg). Os caminhos de leitura compartilham o pool
e o mesmo processo.

### Módulos (`client/services/telemetry_consumer/src/telemetry_consumer/`)

| Módulo | Responsabilidade |
| --- | --- |
| `config.py` | Config via `pydantic-settings` (app_id, RabbitMQ, banco, retry, HTTP). |
| `db.py` | Pool asyncpg, `insert_event` idempotente e `fetch_telemetry` paginado. |
| `consumer.py` | Thread rabbitpy: declara fila+DLQ, bind, consome, ack manual, retry, estado de health. |
| `broadcaster.py` | Registro de WebSockets conectados e broadcast de eventos processados. |
| `routers/telemetry.py` | `GET /telemetry` e `WS /ws/telemetry/{app_id}`. |
| `app.py` | FastAPI, lifespan (pool + thread consumer), `/health`, wiring. |

O stub atual `src/consumer.py` (`MqttConsumer`) é removido. O pacote passa a se
chamar `telemetry_consumer`; `requires-python` alinhado a `>=3.12,<4.0`.

### Fluxo de ingestão

```
routing → exchange topic linx.telemetry
  → fila durável linx.telemetry.{app_id} (bind application.{app_id}.#)
  → thread rabbitpy (manual ack, prefetch)
  → run_coroutine_threadsafe → handler async
  → insert_event (asyncpg, ON CONFLICT DO NOTHING)
  → ack (sucesso ou duplicata)
  → retry esgotado / payload inválido: publish DLQ linx.telemetry.{app_id}.dlq + ack
  → broadcaster: envia o evento aos WebSockets conectados
```

### Fluxo de leitura

```
frontend → GET /telemetry?dev_eui=...&limit=...&before=...
  → asyncpg SELECT ... ORDER BY time DESC
  → resposta {"items": [...], "next_cursor": ...}

frontend → WS /ws/telemetry/{app_id}
  → aceita, registra conexão
  → a cada evento persistido com sucesso: broadcast JSON do registro
```

## Contrato de consumo

### Fila e binding

- Exchange: `topic` durável `linx.telemetry` (já declarado pelo `routing`).
- Fila do tenant: `linx.telemetry.{app_id}`, durável, `auto_delete=false`.
- Binding: `application.{app_id}.#`.
- Fila morta: `linx.telemetry.{app_id}.dlq`, durável. Falha definitiva publica o
  corpo na DLQ via exchange default (`routing_key` = nome da DLQ) e dá ack na
  mensagem original.
- ACK manual; `prefetch` limita mensagens em voo.

### Envelope consumido

```json
{
  "app_id": "206b6a58-...",
  "dev_eui": "ac1f09fffe...",
  "event_type": "up",
  "payload": { "...": "objeto decodificado" },
  "rssi": -90,
  "snr": 7.5,
  "timestamp": "2026-10-08T12:00:00Z"
}
```

- `timestamp` vira a coluna `time` (não `NOW()`).
- `rssi`/`snr` são opcionais.
- Todos os `event_type` são persistidos (não apenas `up`).
- Corpo não-JSON, não-objeto ou sem os campos obrigatórios: `warning`, publica na
  DLQ e ack.

## Persistência

### Esquema (atualizado em `client/db/schema.sql` e `deploy/db/schema.sql`)

Ambos os arquivos são duplicados hoje e devem permanecer iguais.

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    app_id TEXT,
    dev_eui TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    rssi INT,
    snr FLOAT
);

SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS telemetry_dev_eui_time_idx
    ON telemetry (dev_eui, time DESC);

CREATE UNIQUE INDEX IF NOT EXISTS telemetry_dedup_idx
    ON telemetry (dev_eui, time, event_type);
```

### Migração (bancos existentes)

Aplicar uma vez, antes de subir o novo consumer. O `time` está contido na chave
única, requisito do TimescaleDB para índice único em hypertable.

```sql
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS app_id TEXT;
ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS event_type TEXT;
UPDATE telemetry SET event_type = 'up' WHERE event_type IS NULL;
ALTER TABLE telemetry ALTER COLUMN event_type SET NOT NULL;

-- Se já houver duplicatas (dev_eui, time, event_type), deduplicar antes do índice:
DELETE FROM telemetry a USING telemetry b
 WHERE a.ctid < b.ctid
   AND a.dev_eui = b.dev_eui
   AND a.time = b.time
   AND a.event_type = b.event_type;

CREATE UNIQUE INDEX IF NOT EXISTS telemetry_dedup_idx
    ON telemetry (dev_eui, time, event_type);
```

### Insert idempotente (`db.insert_event`)

```sql
INSERT INTO telemetry (time, app_id, dev_eui, event_type, payload, rssi, snr)
VALUES ($1::timestamptz, $2, $3, $4, $5::jsonb, $6, $7)
ON CONFLICT (dev_eui, time, event_type) DO NOTHING
```

Retorna `True` se inseriu (status `INSERT 0 1`), `False` se foi duplicata
(status `INSERT 0 0`). Duplicata é tratada como sucesso para fins de ack.

### Leitura paginada (`db.fetch_telemetry`)

- Filtro opcional por `dev_eui`; serviço é por tenant, então `app_id` é implícito.
- Ordenação `time DESC`; `limit` padrão 100 (máx. 1000).
- Cursor por `before` (timestamp ISO): retorna eventos estritamente anteriores.
- Resposta: `{"items": [ {time, app_id, dev_eui, event_type, payload, rssi, snr} ], "next_cursor": "<time do último item ou null>"}`.

## API de leitura

### `GET /telemetry`

- Query: `dev_eui` (opcional), `limit` (opcional, default 100), `before`
  (opcional, ISO-8601).
- `200` com a lista; `503` se o pool não estiver inicializado.

### `WS /ws/telemetry/{app_id}`

- Aceita a conexão; se `{app_id}` divergir de `APP_ID`, fecha com código de
  política.
- Registra a conexão no `broadcaster`; remove ao desconectar.
- A cada evento persistido com sucesso, envia o registro em JSON a todos os
  WebSockets do app.
- Sem auth neste escopo (documentado como pendência de hardening).

## Resiliência

- ACK só após confirmação do insert.
- Erro transitório de banco: retry in-process `CONSUMER_MAX_RETRIES` com backoff
  `CONSUMER_RETRY_BACKOFF_SECONDS`; esgotado → DLQ + ack.
- Queda de conexão RabbitMQ: reconexão com backoff `RABBIT_CONNECT_MAX_ATTEMPTS`.
- `prefetch` (`RABBIT_PREFETCH_COUNT`) limita mensagens em voo.
- Shutdown gracioso (`SIGTERM`): para a thread, fecha conexão e pool.

## Configuração (env)

| Variável | Default | Uso |
| --- | --- | --- |
| `APP_ID` | `app-abc123` | Identidade do tenant; define fila e binding. |
| `RABBIT_URL` | `amqp://guest:guest@localhost:5672/%2f` | Conexão AMQP. |
| `RABBIT_EXCHANGE` | `linx.telemetry` | Exchange de origem. |
| `RABBIT_PREFETCH_COUNT` | `10` | Mensagens em voo. |
| `RABBIT_CONNECT_MAX_ATTEMPTS` | `5` | Tentativas de conexão. |
| `RABBIT_CONNECT_BACKOFF_SECONDS` | `1.0` | Backoff de reconexão. |
| `CONSUMER_MAX_RETRIES` | `3` | Retries por mensagem. |
| `CONSUMER_RETRY_BACKOFF_SECONDS` | `1.0` | Backoff do retry. |
| `DB_HOST` | `timescaledb` | Host do TimescaleDB. |
| `DB_PORT` | `5432` | Porta. |
| `DB_USER` | `tenant` | Usuário. |
| `DB_PASSWORD` | `changeme` | Senha. |
| `DB_NAME` | `tenantdb` | Banco. |
| `HTTP_HOST` | `0.0.0.0` | Bind do FastAPI. |
| `HTTP_PORT` | `8000` | Porta do FastAPI. |

Fila = `linx.telemetry.{app_id}`; DLQ = `linx.telemetry.{app_id}.dlq`.

## Remoção do `tenant_app`

Arquivos/artefatos a remover:

- `client/src/` (todo o pacote `tenant`, incluindo `grpc/`, `routers/`).
- `client/tests/` (testes do tenant app).
- `client/Dockerfile`, `client/pyproject.toml`, `client/poetry.lock`.
- `client/htmlcov/` (artefato gerado).
- `client/services/teste/` (diretório vazio/estranho).

Mantidos/atualizados:

- `client/db/schema.sql` (novo esquema).
- `client/services/telemetry_consumer/`.
- `client/docker-compose.yml`: reescrito para subir `timescaledb` +
  `telemetry_consumer` (ambiente local).
- `client/README.md`: reescrito para o layout de serviços.

## Ajustes no `client_agent`

Remover o encaminhamento REST, já que o RabbitMQ passa a ser o único caminho de
ingestão:

- Remover `middleware/services/client_agent/src/agent/routers/ingest.py`.
- Remover o `http_client`/`httpx` e o registro do router em
  `middleware/services/client_agent/src/agent/main.py`.
- Remover `tenant_app_url` de `.../agent/config.py` e `TENANT_APP_URL` do
  `.env.example`; remover `httpx` das dependências.
- O `client_agent` fica com `GetAppConfig` (gRPC) e `/health`.

## Infraestrutura e deploy

- `client/services/telemetry_consumer/Dockerfile`: multi-stage simples (poetry,
  sem dependência de `linx_core/shared`), expõe `8000`, comando
  `uvicorn telemetry_consumer.app:app`.
- `deploy/docker-compose.yml`:
  - Remover o serviço `tenant_app` e o `depends_on: tenant_app` do `client_agent`.
  - Adicionar `telemetry_consumer` (build context `../client/services/telemetry_consumer`),
    `depends_on` `timescaledb` healthy e `rabbitmq` healthy, env `APP_ID`,
    `RABBIT_URL`, `DB_*`; porta publicada apenas se necessário para dev (health
    interno).
- `.github/workflows/telemetry-consumer-ci.yml`: `black`, `isort`, `flake8`,
  `mypy`, `pytest --cov-fail-under=70` (paths
  `client/services/telemetry_consumer/**`). Testes unitários com fakes, sem
  serviço de banco.

## Testes

Unitários com fakes, sem broker nem banco real:

- `config`: valores default e override por env.
- `db`: SQL de `insert_event` correto; `True` no insert, `False` no conflito;
  `fetch_telemetry` monta cursor/limite e devolve `next_cursor`.
- `consumer`: envelope válido → handler + ack; duplicata → ack sem DLQ; falha de
  banco após retries → DLQ + ack; JSON inválido → DLQ + ack; reconexão.
- `broadcaster`: registra/remove conexões e faz broadcast.
- `routers`: `GET /telemetry` (com e sem `dev_eui`), `WS` recebe broadcast e
  valida `app_id`.
- `app`: `/health`.

Smoke manual documentado: subir a stack, `mosquitto_pub` de um uplink válido no
tópico ChirpStack, confirmar o registro em `telemetry` e o recebimento via
WebSocket.

## Documentação

- `docs/comunicacao_entre_servicos.md`: substituir `tenant_app` por
  `telemetry_consumer` na topologia, tabela de serviços e fluxos; atualizar a
  seção 5 (ingestão) e a seção 7 (variáveis); remover `TENANT_APP_URL`,
  `CLIENT_AGENT_URL`.
- `docs/middleware/README.md` e `middleware/services/client_agent/README.md`:
  remover descrição do encaminhamento REST e do `tenant_app`.
- `docs/client/README.md` e `client/README.md`: refletir o novo layout.
- `SPRINTS_BACKLOG.md` e `PROGRESS.md`: atualizar referências e marcar a issue.

## Validação

- `pytest` verde em `client/services/telemetry_consumer` com cobertura >= 70%.
- `black --check`, `isort --check`, `mypy`, `flake8` sem erros.
- Stack sobe com `rabbitmq` e `timescaledb` healthy; `telemetry_consumer`
  conecta e declara a fila do tenant.
- `mosquitto_pub` de um uplink válido resulta em registro na hypertable e em
  broadcast no WebSocket.
- Redelivery da mesma mensagem não gera registro duplicado.
- `GET /telemetry` retorna o histórico persistido.
- `client_agent` sobe sem `tenant_app` e sem o router `/ingest`.

## Riscos e mitigações

- **Duplicatas pré-existentes impedem o índice único:** deduplicar antes de criar
  `telemetry_dedup_idx`; a migração documenta o passo.
- **Dois `schema.sql` divergentes:** manter `client/db` e `deploy/db` idênticos;
  a validação confere.
- **Reindexação de hypertable em produção:** o índice único adiciona custo de
  escrita; aceitável no volume atual.
- **WebSocket sem auth:** documentado como pendência de hardening; exposto apenas
  na rede interna.
- **Thread rabbitpy x event loop:** a conexão fica em uma única thread; o
  cruzamento com o loop é feito por `run_coroutine_threadsafe`.
- **Perda de telemetria na transição:** manter a fila de auditoria
  `linx.telemetry.audit` do `routing` até o consumer estar validado.

## Commits

1. `feat(telemetry-consumer): scaffold do serviço, config e pool asyncpg`
2. `feat(telemetry-consumer): persiste envelope do RabbitMQ de forma idempotente`
3. `feat(telemetry-consumer): retry e DLQ por tenant`
4. `feat(telemetry-consumer): GET /telemetry e WebSocket`
5. `build(deploy): substitui tenant_app pelo telemetry_consumer`
6. `refactor(client_agent): remove encaminhamento REST /ingest`
7. `chore(client): remove tenant_app`
8. `docs: atualiza fluxo de ingestão e leitura`
