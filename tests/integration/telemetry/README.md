# Integração — Telemetria ponta-a-ponta

Verifica que uma telemetria percorre o caminho real até o que o frontend
consome:

```
mosquitto do infra (uplink MQTT) -> routing -> rabbitmq
  (exchange por tenant) -> telemetry_consumer (TimescaleDB + WebSocket)
```

Contratos do frontend cobertos: `GET /telemetry` (histórico REST) e
`WS /ws/telemetry/{app_id}` (tempo real, RNF-003).

## Montagem da stack

A suíte usa os **serviços reais**, mas em uma montagem própria de teste:

| Serviço | Origem |
|---|---|
| Mosquitto | `infra/docker-compose.yml` |
| RabbitMQ | `infra/docker-compose.base.yml` |
| `routing` | build de `middleware/services/routing/Dockerfile` |
| `telemetry_consumer` | build de `client/services/telemetry_consumer/Dockerfile` |
| TimescaleDB | imagem pública + `client/db/schema.sql` |

O arquivo que junta esses serviços é
`tests/integration/telemetry/docker-compose.stack.yml`. Ele **não substitui**
os composes de aplicação: apenas declara o conjunto que a suíte sobe, com
portas em offsets de teste e rede isolada.

A stack roda na rede `lynx-it-network` (parametrizada por `LINX_NETWORK`),
separada do ambiente de desenvolvimento. O `rabbitmq` usa as portas de teste
`5673`/`15673` via `docker-compose.broker-override.yml`.

## Casos de teste

1. Uplink MQTT → WS em ≤ 2s + REST + TimescaleDB
2. Envelope AMQP → persistido + broadcast
3. Deduplicação por `(app_id, dev_eui, time, event_type)`
4. Payload inválido → não persiste (DLQ)
5. Regressão: `timestamp` string ISO aceito pelo consumer

## Rodar

```bash
make integration            # da raiz do repo
# ou
tests/integration/run.sh
```

Inspecionar a stack manualmente:

```bash
bash scripts/bootstrap-network.sh lynx-it-network
LINX_NETWORK=lynx-it-network docker compose -p lynx-integration \
  --env-file tests/integration/telemetry/test.env \
  -f tests/integration/telemetry/docker-compose.stack.yml \
  -f infra/docker-compose.base.yml \
  -f tests/integration/telemetry/docker-compose.broker-override.yml \
  up -d --build --wait rabbitmq timescaledb telemetry_consumer routing
LINX_NETWORK=lynx-it-network docker compose -p lynx-integration ... ps
LINX_NETWORK=lynx-it-network docker compose -p lynx-integration ... down -v
```

O Mosquitto é gerenciado separadamente pelo projeto `lynx-integration-infra`,
usando `infra/docker-compose.yml` e
`tests/integration/telemetry/docker-compose.infra-override.yml`. Ele sobe na
mesma rede isolada.
