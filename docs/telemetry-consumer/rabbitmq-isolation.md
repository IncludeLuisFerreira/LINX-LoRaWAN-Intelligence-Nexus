# Isolamento por tenant no RabbitMQ

Documento do modelo de isolamento por aplicação usado pelo `telemetry_consumer`.
Cada tenant tem exchange, fila, DLQ e usuário próprios no RabbitMQ, com permissões
restritas ao seu namespace. O `identity_api` provisiona a credencial na criação da
aplicação; o `routing` publica no exchange do tenant.

Referências: `docs/comunicacao_entre_servicos.md` (§5),
`docs/superpowers/specs/2026-10-12-rabbitmq-tenant-isolation-design.md`.

## Topologia

Vhost único (`/`). Todos os nomes derivam do `app_id` (UUID da aplicação):

| Recurso            | Nome                              | Papel                                             |
| :----------------- | :-------------------------------- | :------------------------------------------------ |
| Exchange           | `linx.telemetry.{app_id}`         | Ponto de publicação do tenant (`topic`, durável). |
| Fila               | `linx.telemetry.{app_id}`         | Consumo da telemetria do tenant.                  |
| DLQ                | `linx.telemetry.{app_id}.dlq`     | Falha definitiva / payload inválido.              |
| DLX                | `linx.telemetry.{app_id}.dlx`     | Exchange direta da DLQ; evita o default exchange. |
| Fila de auditoria  | `linx.telemetry.audit`            | Binding `#` em todos os exchanges; admin-only.    |
| Usuário            | `tenant.{app_id}`                 | Credencial do cliente.                            |
| Binding            | `application.{app_id}.#`          | Liga o exchange do tenant à fila do tenant.       |

```
routing (admin)
  → exchange topic linx.telemetry.{app_id}
      → fila linx.telemetry.{app_id}     (bind application.{app_id}.#)
      → fila linx.telemetry.audit        (bind #, todos os tenants)

telemetry_consumer (tenant.{app_id})
  → exchange linx.telemetry.{app_id}     (declare; configure do próprio namespace)
  → fila linx.telemetry.{app_id}         (consume)
  → exchange DLX linx.telemetry.{app_id}.dlx  (declare; publish da DLQ)
  → DLQ linx.telemetry.{app_id}.dlq      (bind à DLX; consume)
```

## Permissões

Uma única regex é aplicada a `configure`, `write` e `read`:

```
^linx\.telemetry\.{app_id}(\.|$)
```

O isolamento é por **nome do recurso** (não por tópico roteado): o usuário do tenant
só declara, publica e consome recursos cujo nome está no seu prefixo.

- `configure`: declara/remove o exchange, a DLX e as filas do tenant.
- `write`: publica no exchange do tenant e na DLX (`linx.telemetry.{app_id}.dlx`).
  A DLQ é populada por publish na DLX nomeada — nunca no default exchange `""`,
  pois o RabbitMQ valida `write` no `amq.default` (não na routing key), que está
  fora desta regex; publicar ali seria negado e causaria loop de redelivery.
- `read`: consome a fila do tenant e a DLQ.
- Não casa `linx.telemetry.audit` nem `linx.telemetry.{outro_app}`.

## Credenciais

- O usuário do tenant é `tenant.{app_id}`.
- A senha é **determinística**: `base64url(HMAC-SHA256(app_id, segredo))`,
  truncada em 40 caracteres (`RABBITMQ_TENANT_SECRET` é o segredo do servidor).
  Não há senha armazenada no banco de controle.
- O `Linx Core` deriva a senha, provisiona o usuário/permissões e monta o
  `RABBIT_URL` (`amqp://tenant.{app_id}:{senha}@host:5672/%2f`) para o stack do
  cliente. O cliente **não** recebe o segredo.
- Helper local: `deploy/scripts/provision-rabbitmq-tenant.sh`.

## Provisionamento

O `identity_api` provisiona a credencial na criação da aplicação (e remove na
exclusão), via management API do RabbitMQ:

1. `PUT /api/users/{tenant.{app_id}}` com a senha derivada.
2. `PUT /api/permissions/{vhost}/{tenant.{app_id}}` com o regex do namespace.

Ordem: ChirpStack → provisionamento RabbitMQ → commit no DB. Se o provisionamento
falhar, a aplicação é removida do ChirpStack (best-effort) e a resposta é `502`. Se
o commit falhar, o usuário RabbitMQ e a aplicação no ChirpStack são removidos
(best-effort).

## Configuração do `telemetry_consumer`

| Variável   | Default                             | Uso                                                  |
| :--------- | :---------------------------------- | :--------------------------------------------------- |
| `APP_ID`   | `app-abc123`                        | `app_id` real; define exchange, fila, DLQ e binding. |
| `RABBIT_URL` | `amqp://guest:guest@localhost:5672/%2f` | URL com a credencial do tenant.                 |

Exchange = `linx.telemetry.{app_id}`; fila = `linx.telemetry.{app_id}`;
DLQ = `linx.telemetry.{app_id}.dlq`; binding = `application.{app_id}.#`.

## Falha de credencial/permissão

Falha de acesso (`ACCESS_REFUSED`, reply code 403) é logada em nível `error` com a
causa e registrada em `last_error` (visível em `GET /health`). O serviço **não**
encerra: reconecta com o backoff configurado. Como a falha é permanente até a
credencial/permissão ser corrigida, o `/health` é o sinal operacional.

## Verificação de isolamento

Teste de integração (broker real) em
`client/services/telemetry_consumer/tests/test_isolation_integration.py`, marcado
`integration` e pulado quando o broker/credenciais não estão no ambiente. Cobre:

1. Consumer A recebe apenas telemetria de A.
2. Consumer A não lê `linx.telemetry.audit`.
3. Consumer A não declara/publica fora do seu namespace (access-refused).
4. A auditoria recebe mensagens de todos os tenants.

Smoke manual:

```bash
# publicar na exchange do tenant A (admin) e no B; verificar que só A recebe
# e que B não lê a fila de auditoria.
```
