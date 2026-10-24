# Tenant App (container mínimo)

Imagem Docker mínima provisionada por aplicação no Linx Core. Ela serve para
validar o fluxo da issue #58 sem subir o `telemetry_consumer` completo:

- `GET /health` — público, usado pelo healthcheck do container.
- `GET /info` — exige `X-Service-Token`; devolve `app_id`, `mqtt_topic` e
  `db_password_configured` (booleano). Nunca devolve `DB_PASSWORD`.

## Build

```bash
docker build -t linx-tenant-app:latest client/tenant_app
# ou, na raiz:
make build-tenant-image
```

## Variáveis de ambiente

| Variável | Uso |
| -------- | --- |
| `APP_ID` | UUID da aplicação, retornado em `/health` e `/info`. |
| `MQTT_TOPIC` | Tópico de uplink do tenant. |
| `SERVICE_TOKEN` | Token de serviço validado em `/info` e injetado pelo provisioner. |
| `DB_PASSWORD` | Senha efêmera gerada pelo provisioner; nunca é exposta. |

## Execução local

```bash
docker run --rm -p 8000:8000 \
  -e APP_ID=check-app \
  -e MQTT_TOPIC='application/check-app/device/+/event/up' \
  -e DB_PASSWORD=check-db-password \
  -e SERVICE_TOKEN=check-service-token-0123456789abcdef \
  linx-tenant-app:latest
```

## Testes

```bash
poetry -C client/tenant_app install
poetry -C client/tenant_app run pytest -q
```

> Esta imagem é um alvo de validação do provisionamento. O runtime completo do
> tenant continua em `client/services/telemetry_consumer` + `client/frontend`.
