# Isolamento por tenant no RabbitMQ (`telemetry_consumer`)

- **Data:** 2026-10-12
- **Status:** Proposto
- **Issue:** #200 (`feat(client): telemetry_consumer com isolamento por tenant no RabbitMQ`)
- **Escopo:** Garantir isolamento por aplicação no RabbitMQ para a ingestão de
  telemetria. Cada aplicação passa a ter exchange, fila, DLQ e usuário próprios.
  O `routing` publica no exchange do tenant; o `telemetry_consumer` consome com
  credencial restrita; o `Linx Core` (`identity_api`) provisiona a credencial e as
  permissões na criação da aplicação.

## Contexto

Hoje o isolamento é apenas convenção:

- O `routing` publica no exchange `topic` durável `linx.telemetry` (vhost `/`) com
  routing key `application.{app_id}.device.{dev_eui}.{event_type}`
  (`middleware/services/routing/src/routing/envelope.py:6`,
  `middleware/services/routing/src/routing/publisher.py:81`).
- O `routing` também declara a fila de auditoria `linx.telemetry.audit` com binding
  `#` (`publisher.py:40`).
- Cada `telemetry_consumer` declara a fila `linx.telemetry.{app_id}` com binding
  `application.{app_id}.#`
  (`client/services/telemetry_consumer/src/telemetry_consumer/config.py:27`,
  `consumer.py:100`).
- Todos os serviços usam o usuário administrativo compartilhado (`RABBIT_URL`).

Nada no broker impede um cliente de declarar uma fila com binding `#` (ou
`application.{outro_app}.#`), consumir telemetria de outra aplicação ou ler a fila
de auditoria. Não há confidencialidade nem integridade por aplicação.

O `APP_ID` no `deploy/.env` foi um paliativo de teste. O cliente passa a usar o
`app_id` real da aplicação cadastrada (o UUID gerado pelo ChirpStack e persistido
no `identity_api`).

## Decisões aprovadas

1. **`app_id` real.** O `telemetry_consumer` opera com o `app_id` real da aplicação
   (UUID persistido no `identity_api`), não com um valor de teste no `.env`.
2. **Senha determinística.** A senha do usuário RabbitMQ por tenant é derivada por
   HMAC (app_id + segredo do servidor), sem armazenamento de senha no banco de
   controle.
3. **Auditoria para todos.** A fila de auditoria recebe os dados de todos os
   exchanges de tenant (binding `#` em cada exchange), servindo observabilidade
   futura.
4. **Roteamento por nome.** O isolamento se dá pelo **nome do recurso** conter
   `.app_id`: permissões `configure`/`write`/`read` com regex sobre o nome da fila
   e do exchange. Não é autorização por tópico roteado.
5. **Cliente HTTP oficial.** O `identity_api` usa `httpx` (substitui a dependência
   `httpx2` de desenvolvimento).

## Objetivos

1. Definir topologia por tenant: exchange `linx.telemetry.{app_id}` (topic,
   durável), fila `linx.telemetry.{app_id}` (durável), DLQ
   `linx.telemetry.{app_id}.dlq` (durável) e binding `application.{app_id}.#`.
2. Fazer o `routing` publicar no exchange do tenant, derivando o `app_id` do
   envelope/uplink.
3. Provisionar, na criação da aplicação, um usuário RabbitMQ por tenant com
   permissões restritas ao prefixo `^linx\.telemetry\.{app_id}(\.|$)`.
4. Garantir que a fila de auditoria receba mensagens de **todos** os tenants e que
   nenhum tenant possa lê-la.
5. Tratar falha de credencial/permissão com log explícito e reconexão, sem derrubar
   o serviço em silêncio.

## Não-objetivos

- Frontend/WebSocket (issue #43).
- Autenticação JWT/RBAC e TLS no RabbitMQ (Sprint 5).
- Reconexão de WebSocket (#100) e polling fallback (#44).
- Orquestração completa do deploy do stack do cliente (como o container do tenant
  recebe as variáveis). Este spec define e valida o contrato de topologia,
  credenciais e provisionamento; o mecanismo de injeção é documentado, não
  implementado como plataforma de deploy.
- Rotação automática de senha.

## Arquitetura

Vhost único (`/`). Um exchange por aplicação. Um usuário RabbitMQ por aplicação.
Todos os nomes derivam do `app_id`.

```
routing (usuário admin)
  → exchange topic durável linx.telemetry.{app_id}
      → fila linx.telemetry.{app_id}          (bind application.{app_id}.#)
      → fila linx.telemetry.audit             (bind #, todos os tenants)
  → default exchange ""                        (DLQ)

telemetry_consumer (usuário tenant.{app_id})
  → exchange linx.telemetry.{app_id}          (declare, configure próprio)
  → fila linx.telemetry.{app_id}              (consume)
  → DLQ linx.telemetry.{app_id}.dlq           (publish via default exchange)
```

### Namespace por aplicação

| Recurso | Nome | Papel |
| --- | --- | --- |
| Exchange | `linx.telemetry.{app_id}` | Ponto de publicação do tenant. |
| Fila | `linx.telemetry.{app_id}` | Consumo da telemetria do tenant. |
| DLQ | `linx.telemetry.{app_id}.dlq` | Falha definitiva / payload inválido. |
| Fila de auditoria | `linx.telemetry.audit` | Binding `#` em cada exchange de tenant. Admin only. |
| Usuário | `tenant.{app_id}` | Credencial do cliente. |
| Binding | `application.{app_id}.#` | Liga exchange do tenant à fila do tenant. |

### Permissões do usuário do tenant

Uma única regex aplicada a `configure`, `write` e `read`:

```
^linx\.telemetry\.{app_id}(\.|$)
```

`{app_id}` é um UUID (sem meta-caracteres de regex), mas o valor é escapado ao
montar a expressão, por robustez. Consequências:

- `configure`: só declara/remove `linx.telemetry.{app_id}`,
  `linx.telemetry.{app_id}.dlq`.
- `write`: só publica nesses nomes (cobre o publish da DLQ no default exchange).
- `read`: só consome a fila `linx.telemetry.{app_id}`.
- Não casa `linx.telemetry.audit` nem `linx.telemetry.{outro_app}`.

### Segredos

- O segredo do servidor é `RABBITMQ_TENANT_SECRET` (nova variável, no `identity_api`
  e no ambiente de provisionamento).
- Senha do tenant:
  `password = base64url(HMAC-SHA256(secret, app_id))` truncada em 40 caracteres.
- O `Linx Core` deriva a senha, provisiona o usuário e monta o `RABBIT_URL`
  (`amqp://tenant.{app_id}:{password}@host:5672/%2f`) entregue ao stack do cliente.
  O cliente **não** recebe o segredo; recebe a URL já montada.

### Módulos

| Módulo | Mudança |
| --- | --- |
| `middleware/services/routing/src/routing/publisher.py` | Declara e publica no exchange do tenant; liga a auditoria a cada exchange. |
| `middleware/services/routing/src/routing/routing.py` | Propaga o `app_id` ao publisher. |
| `middleware/services/routing/src/routing/config.py` | Prefixo do exchange. |
| `client/services/telemetry_consumer/src/telemetry_consumer/config.py` | `rabbit_exchange` derivado de `app_id`. |
| `client/services/telemetry_consumer/src/telemetry_consumer/consumer.py` | Declara exchange do tenant; trata acesso negado. |
| `linx_core/services/identity_api/src/identity_api/rabbitmq_client.py` | **Novo.** Client da management API. |
| `linx_core/services/identity_api/src/identity_api/routes/application.py` | Provisiona/remove usuário na criação/exclusão. |
| `linx_core/services/identity_api/src/identity_api/config.py` | Config de management/segredo. |
| `linx_core/services/identity_api/src/identity_api/dependencies.py` | Provider do client. |

### `routing`

- `RabbitPublisher` mantém um cache dos exchanges já declarados e das bindings de
  auditoria já aplicadas, para evitar redeclaração a cada mensagem.
- `publish(routing_key, body, app_id)`:
  1. Garante o exchange `linx.telemetry.{app_id}` (topic, durável) e a binding da
     auditoria (`linx.telemetry.audit`, `#`).
  2. Publica com a routing key `application.{app_id}.device.{dev_eui}.{event_type}`.
- Em queda de conexão, o cache é limpo (o broker pode ter perdido declarações em
  reinício, embora duráveis persistam; redeclarar é idempotente).

### `telemetry_consumer`

- `ConsumerSettings.rabbit_exchange` passa a ser propriedade:
  `f"linx.telemetry.{self.app_id}"`.
- `_open` declara o exchange do tenant, a fila e a DLQ, e faz o bind.
- `RABBIT_URL` usa a credencial do tenant.
- Acesso negado (AMQP `ACCESS_REFUSED`, reply code 403 / `ProbableAuthenticationError`)
  é tratado:
  - log em nível `error` com a causa (não `warning` genérico);
  - `_last_error` atualizado (visível em `GET /health`);
  - reconexão com o backoff configurado, sem encerrar o processo.

### `identity_api`

- `RabbitMQClient` (novo) encapsula a management API HTTP:
  - `put_user(user, password)` → `PUT /api/users/{user}` body
    `{"password": "...", "tags": ""}`.
  - `set_permissions(vhost, user, regex)` → `PUT /api/permissions/{vhost}/{user}`
    body `{"configure": regex, "write": regex, "read": regex}`.
  - `delete_user(user)` → `DELETE /api/users/{user}`.
  - Erros HTTP viram `ExternalServiceError`.
- `create_application` (`routes/application.py`): após persistir a aplicação no DB,
  provisiona o usuário e as permissões. Se o DB falhar, remove o usuário
  best-effort. Se o provisionamento falhar, responde `502` e reverte o DB
  (o usuário RabbitMQ não é criado; nada a limpar).
- `delete_application`: remove o usuário best-effort após deletar no ChirpStack e no
  DB.
- Ordem de provisionamento: provisiona depois do commit (o `app_id` só existe após
  a criação no ChirpStack, que já ocorre antes do commit).
- Função de derivação: `derive_tenant_password(app_id, secret)` e
  `build_tenant_rabbit_url(app_id, secret, host, vhost)` em
  `linx_core/shared` (reuso pelo provisionamento e por scripts de deploy).

## Contrato de configuração (env)

### `telemetry_consumer`

| Variável | Default | Uso |
| --- | --- | --- |
| `APP_ID` | `app-abc123` | `app_id` real; define exchange, fila, DLQ e binding. |
| `RABBIT_URL` | `amqp://guest:guest@localhost:5672/%2f` | URL com credencial do tenant. |
| Demais | inalterados | Prefetch, retries, banco, HTTP. |

Exchange = `linx.telemetry.{app_id}`; fila = `linx.telemetry.{app_id}`;
DLQ = `linx.telemetry.{app_id}.dlq`; binding = `application.{app_id}.#`.

### `identity_api`

| Variável | Default | Uso |
| --- | --- | --- |
| `RABBITMQ_MANAGEMENT_URL` | `http://rabbitmq:15672` | Management API. |
| `RABBITMQ_ADMIN_USER` | `linx` | Usuário admin (provisionamento). |
| `RABBITMQ_ADMIN_PASSWORD` | `changeme` | Senha admin. |
| `RABBITMQ_VHOST` | `/` | Vhost (`%2F` na URL). |
| `RABBITMQ_TENANT_SECRET` | `changeme` | Chave HMAC da senha determinística. |
| `RABBITMQ_AMQP_HOST` | `rabbitmq:5672` | Host AMQP para montar o `RABBIT_URL`. |

## Tratamento de erros

- **Provisionamento falha na criação da aplicação:** ordem
  ChirpStack → provisionamento RabbitMQ → commit no DB. Se o provisionamento
  falhar, `identity_api` responde `502` e remove a aplicação do ChirpStack
  best-effort, sem persistir. Se o commit falhar, remove o usuário do RabbitMQ e a
  aplicação do ChirpStack (best-effort). Em nenhum caso a aplicação fica persistida
  sem namespace no broker, nem o namespace fica órfão.
- **Credencial inválida ou sem permissão no cliente:** `telemetry_consumer` loga
  `error`, marca `_last_error` e reconecta com backoff; o `/health` expõe a falha.
- **Auditoria:** falha ao ligar a auditoria ao exchange não impede a publicação no
  tenant (a auditoria é observabilidade, não caminho de dado); loga `warning`.

## Testes

Unitários com fakes (sem broker), conforme suíte atual:

- `telemetry_consumer/config`: `rabbit_exchange` derivado; override por env.
- `telemetry_consumer/consumer`: declara o exchange do tenant; bind correto; DLQ no
  default exchange com a routing key da DLQ; acesso negado → log `error` +
  `_last_error` + reconexão; reconexão após queda; retry esgotado → DLQ.
- `telemetry_consumer/app`: `/health` reflete `_last_error` no estado.
- `routing/publisher`: publica no exchange do tenant correto por `app_id`; declara
  exchange e liga auditoria sob demanda; cache evita redeclaração.
- `routing/routing`: `app_id` propagado do uplink ao publisher.
- `identity_api/rabbitmq_client`: monta `PUT /api/users` e `PUT /api/permissions`
  com usuário e regex corretos; `DELETE`; erro HTTP → `ExternalServiceError`.
- `identity_api/application`: create provisiona; falha de provisionamento →
  `502`; delete remove usuário best-effort.
- `linx_shared`: `derive_tenant_password` determinística; `build_tenant_rabbit_url`
  monta URL com escape.

Integração (broker real, marcado `integration`):

1. Provisionar dois tenants (A, B). Publicar telemetria em A e B.
2. Consumer A recebe apenas mensagens de A.
3. Consumer A não consegue ler `linx.telemetry.audit`.
4. Consumer A não consegue declarar fila `#` nem publicar fora do seu prefixo
   (access-refused).
5. A fila de auditoria recebe mensagens de A e de B.

Cobertura alvo: > 70% do código novo/alterado (`--cov-fail-under=70` mantido no
`telemetry-consumer-ci.yml`; `backend-ci.yml` cobre o `identity_api`).

## Documentação

- Atualizar `docs/comunicacao_entre_servicos.md`: §5 (exchange por tenant, auditoria
  agregada, sequência) e §7 (variáveis).
- Novo `docs/telemetry-consumer/rabbitmq-isolation.md`: topologia, credenciais,
  permissões e config.
- Atualizar `docs/telemetry-consumer/migration.md`: mover a fila existente do
  exchange antigo.
- Atualizar `deploy/.env.example` e `linx_core/.env.example`.

## Infraestrutura e deploy

- `deploy/docker-compose.yml`:
  - `telemetry_consumer`: `RABBIT_URL` com credencial do tenant.
  - `identity_api`: `RABBITMQ_MANAGEMENT_URL`, `RABBITMQ_ADMIN_*`,
    `RABBITMQ_TENANT_SECRET`.
  - `routing`: mantém credencial admin.
- `deploy/scripts/`: helper de provisionamento/bootstrap para o ambiente local
  (cria o usuário do tenant usando a mesma derivação).

## Migração (bancos e broker existentes)

- A fila `linx.telemetry.{app_id}` existente está bindada ao exchange antigo
  `linx.telemetry`. Passos: criar o exchange `linx.telemetry.{app_id}`, criar o
  usuário do tenant, re-bindar a fila ao novo exchange, drenar mensagens em voo,
  remover a binding antiga.
- Enquanto não houver consumidor validado no novo exchange, manter a fila de
  auditoria ativa para não perder telemetria.

## Riscos

- **Ordem de provisionamento x commit:** definir a sequência exata para não deixar
  aplicação sem namespace nem namespace órfão. Mitigação: rollback best-effort nas
  duas direções, como já feito para o ChirpStack.
- **Segredo determinístico:** vazamento do segredo permite derivar todas as senhas.
  Mitigação: segredo forte, restrito ao `identity_api`/provisionamento, documentado
  como pendência de rotação.
- **`linx.telemetry.audit` como prefixo colidente:** um `app_id` igual a `audit`
  colidiria; mitigação: `app_id` é UUID, validado no `validation.py`
  (`^[A-Za-z0-9_-]+$`); documentado.
- **Auditoria agrega todos os tenants:** é intencional (observabilidade futura); a
  permissão de leitura é admin-only.
- **Teste de integração precisa de broker:** adicionar RabbitMQ como service
  container no CI ou manter o teste marcado; risco de cobertura se não rodar.
- **Retry infinito em credencial inválida:** `ACCESS_REFUSED` é permanente; o
  backoff evita spam, mas o serviço nunca recupera sem correção da credencial.
  Mitigação: `_last_error` visível no `/health` e log `error`.

## Commits previstos

1. `feat(identity_api): cliente da management API do RabbitMQ e provisionamento por tenant`
2. `feat(routing): publica no exchange por tenant e agrega auditoria`
3. `feat(telemetry_consumer): exchange por tenant e tratamento de acesso negado`
4. `build(deploy): credenciais por tenant no compose`
5. `test: isolamento por tenant no RabbitMQ`
6. `docs: topologia e credenciais de isolamento no RabbitMQ`
