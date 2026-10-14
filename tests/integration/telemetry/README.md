# Integração — Telemetria ponta-a-ponta

Verifica que uma telemetria percorre o caminho real até o que o frontend
consome:

```
mosquitto (uplink MQTT) -> routing -> rabbitmq (exchange por tenant)
  -> telemetry_consumer (persiste TimescaleDB + broadcast WebSocket)
```

Contratos do frontend cobertos: `GET /telemetry` (histórico REST) e
`WS /ws/telemetry/{app_id}` (tempo real, RNF-003).

## Reúso da stack real

Esta suíte **não define serviços próprios**. Usa o compose real
`deploy/docker-compose.yml` como base e aplica
`docker-compose.override.yml` para:

- publicar portas em offsets de teste (loopback);
- fixar `APP_ID=integration-app` e apontar o consumer para a credencial
  administrativa do broker (sem provisionamento por-tenant).

Sobe apenas os serviços do caminho: `mosquitto`, `routing`, `rabbitmq`,
`timescaledb`, `telemetry_consumer`.

Variáveis exigidas pelo compose base ficam em `test.env` (valores de teste).

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
docker compose -p lynx-integration \
  --env-file telemetry/test.env \
  -f ../../deploy/docker-compose.yml \
  -f telemetry/docker-compose.override.yml \
  up -d --build --wait mosquitto routing rabbitmq timescaledb telemetry_consumer
docker compose -p lynx-integration ... ps
docker compose -p lynx-integration ... down -v
```
