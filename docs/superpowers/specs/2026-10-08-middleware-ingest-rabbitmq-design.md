# Middleware ingest: MQTT ChirpStack → exchange RabbitMQ

- **Data:** 2026-10-08
- **Status:** Proposto
- **Escopo:** Redesenho do serviço `middleware/services/routing` para consumir a
  telemetria do ChirpStack via MQTT, validar a integridade da mensagem e
  publicá-la em um exchange `topic` do RabbitMQ. O middleware deixa de resolver
  o destino (tenant / endpoint do Client Agent) e passa a apenas publicar.

## Contexto

Hoje o serviço `middleware/services/routing` (`UplinkRouter` em
`src/routing/routing.py`) consome o tópico MQTT de uplink do ChirpStack e faz
`POST` HTTP direto no `/ingest` do Client Agent dono do dispositivo. Para
descobrir o destino, consulta a tabela `device_routes` por `dev_eui`
(`routing.py:194`) e aplica allowlist anti-SSRF, retry e cap de payload.

Esse desenho coloca responsabilidade de roteamento por tenant dentro do
middleware: cada novo destino (novo cliente, nova aplicação, alerta,
analytics) exige alterar o middleware. Também mistura o plano de ingestão com
o plano de distribuição.

O tópico consumido (`application/+/device/+/event/up`, `config.py:7`) e o broker
(`MQTT_BROKER_HOST=mosquitto`, porta `1883`) coincidem com o que o ChirpStack
publica (`infra/configuration/chirpstack/chirpstack.toml:104-106`), então a
origem do dado já é a correta. O que muda é o destino.

O objetivo central do middleware passa a ser: **pegar a telemetria, verificar a
integridade da mensagem e publicá-la em um exchange do RabbitMQ**. A
distribuição para o consumidor final passa a ser dinâmica, feita por filas e
bindings no RabbitMQ — criar um novo consumidor não exige tocar no middleware.

### Aviso de nomenclatura

A documentação (`docs/comunicacao_entre_servicos.md`) ainda descreve um
`client_agent (mqtt_consumer)` que não existe mais (removido no hotfix
`docs/superpowers/plans/2026-10-06-hotfix-sprint3-review.md`). O consumer real
está no `middleware/services/routing`. A documentação deve ser corrigida na
implementação.

## Objetivo

Transformar `routing` em um serviço de ingestão responsável por:

1. Consumir o tópico de uplink do ChirpStack no broker MQTT (QoS 1).
2. Validar a integridade da mensagem (estrutural) e descartar inválidas com log.
3. Publicar um envelope normalizado em um exchange `topic` do RabbitMQ, com
   routing key hierárquica derivada do tópico.

O roteamento para consumidores finais é responsabilidade dos consumidores, via
filas e bindings no RabbitMQ.

## Não-objetivos

- Migrar `client_agent` ou `tenant_app` para consumir do RabbitMQ. Fica para um
  spec seguinte.
- Remover a tabela `device_routes`, o endpoint `POST /ingest` do Client Agent
  ou a allowlist do repositório. Neste escopo, apenas o consumer deixa de
  usá-los.
- Deduplicação por `f_cnt`/duplicata.
- Verificação de autenticidade/assinatura do payload.
- Buffer em disco (spool) para sobreviver a queda prolongada do RabbitMQ.
- Reescrever o serviço em asyncio.

## Arquitetura

Um único serviço de ingestão, com módulos separados por responsabilidade. A
decisão por não decompor o ingest em múltiplos contêineres é consciente: as
tarefas são lineares (consumir → validar → publicar) e dividi-las exigiria
outro hop de mensageria entre os estágios, aumentando pontos de falha sem
ganho de manutenção. O fan-out de serviços independentes acontece **do lado dos
consumidores**, através de filas e bindings no exchange.

### Módulos (dentro de `src/routing/`)

| Módulo | Responsabilidade |
| --- | --- |
| `config.py` | Configuração via `pydantic-settings` (MQTT + Rabbit). |
| `consumer.py` | Cliente paho: assina o tópico, enfileira mensagens validadas. |
| `validation.py` | Integridade estrutural e extração de `app_id`/`dev_eui`/`event_type`. |
| `envelope.py` | Monta o envelope normalizado e a routing key. |
| `publisher.py` | Conexão/channel rabbitpy, declara o exchange, publica com confirms. |
| `app.py` (ou `main` no `routing.py`) | Wiring, sinais, shutdown. |

### Fluxo

```
ChirpStack → Mosquitto (topic up)
  → consumer (paho, QoS 1)
  → validation (estrutural; descarta inválidas)
  → queue.Queue interna (cap 1000)
  → publisher (thread única, rabbitpy, publisher confirms)
  → exchange topic "linx.telemetry"
  → filas/bindings dos consumidores
```

## Contrato

### Routing key

Formato: `application.{app_id}.device.{dev_eui}.{event_type}`

Exemplo: `application.206b6a58-.../device.ac1f09.../event.up`.

Derivada diretamente das partes do tópico MQTT. Os separadores de path do
tópico (`application/<app_id>/device/<dev_eui>/event/<event_type>`) são
reescritos para o formato com pontos da routing key. Binding do consumidor por
tenant: `application.{app_id}.#`; por dispositivo: `#.device.{dev_eui}.#`.

### Envelope publicado

Corpo JSON, propriedades `content_type=application/json` e `delivery_mode=2`
(persistente):

```json
{
  "app_id": "206b6a58-...",
  "dev_eui": "ac1f09fffe...",
  "event_type": "up",
  "payload": { "...": "event.object" },
  "rssi": -90,
  "snr": 7.5,
  "timestamp": "2026-10-08T12:00:00Z"
}
```

- `payload`: objeto `object` do evento ChirpStack (payload decodificado do
  sensor). Se ausente ou não for objeto, a mensagem é descartada.
- `rssi`/`snr`: do primeiro item de `rxInfo`, quando presentes (mesma lógica de
  `build_ingest_payload`, `routing.py:46`).
- `timestamp`: `event.time` do ChirpStack.

### Validação de integridade (estrutural)

A mensagem é descartada com `warning` (nunca publicada, nunca lança exceção
para fora do callback) quando:

1. payload MQTT excede `max_payload_bytes` (64 KiB);
2. payload não é JSON válido ou não é um objeto;
3. `app_id`, `dev_eui` ou `event_type` não são extraíveis do tópico;
4. `object.payload` ausente ou não é objeto;
5. `timestamp` ausente.

### Garantia de entrega

- Exchange `topic` **durável**; mensagens **persistentes** (`delivery_mode=2`).
- `channel.enable_publisher_confirms()` no channel de publicação; o retorno de
  `message.publish(...)` indica confirmação do broker.
- Publish não confirmado ou conexão indisponível: retry com backoff (até 5
  tentativas). Esgotadas as tentativas, `error` + descarta (sem spool).
- Conexão cai em runtime: reabre com backoff.
- Fila interna cheia: descarta a mensagem mais nova com `error`.

## Configuração

`src/routing/config.py` (remove `http_timeout_seconds` e
`agent_endpoint_allowlist`):

| Variável | Default | Uso |
| --- | --- | --- |
| `MQTT_BROKER_HOST` | `mosquitto` | broker MQTT (já existe) |
| `MQTT_BROKER_PORT` | `1883` | porta MQTT (já existe) |
| `MQTT_TOPIC` | `application/+/device/+/event/up` | tópico (já existe) |
| `MQTT_QOS` | `1` | QoS do subscribe (novo) |
| `RABBIT_URL` | `amqp://guest:guest@rabbitmq:5672/%2f` | conexão rabbitpy (novo) |
| `RABBIT_EXCHANGE` | `linx.telemetry` | exchange `topic` durável (novo) |
| `MAX_PAYLOAD_BYTES` | `65536` | cap de payload (já existe) |
| `RABBIT_CONNECT_MAX_ATTEMPTS` | `5` | tentativas de conexão (novo) |
| `RABBIT_CONNECT_BACKOFF_SECONDS` | `1.0` | backoff (novo) |

O serviço **não** usa mais `DATABASE_URL` nem o model `DeviceRoute`.

## Infraestrutura e deploy

`deploy/docker-compose.yml`:

- Adicionar service `rabbitmq` (`rabbitmq:3-management`), volume para dados,
  healthcheck `rabbitmq-diagnostics -q ping`, portas `5672` e `15672`.
- `routing` passa a depender de `rabbitmq: condition: service_healthy`; recebe
  `RABBIT_URL` e `RABBIT_EXCHANGE`; perde `DATABASE_URL`.
- `routing` mantém `depends_on` de `mosquitto`.

Dependências (`middleware/services/routing/pyproject.toml`): adicionar
`rabbitpy` (`>=3.0,<4.0`). Remover `httpx`, `sqlalchemy` e `psycopg`, que só
existiam para o POST HTTP e o lookup em `device_routes`. Manter `paho-mqtt`,
`pydantic-settings` e `linx-shared` (base de `Settings`).

## Testes

Testes unitários com fakes, sem broker real:

- `validation`: descarta payload grande, JSON inválido, não-objeto, tópico sem
  `app_id`/`dev_eui`/`event_type`, `object` ausente, `timestamp` ausente;
  aceita evento válido.
- `envelope`: `build_envelope` mapeia campos corretamente; `routing_key`
  formata `application.{app_id}.device.{dev_eui}.{event_type}`.
- `publisher`: drena a fila e chama `publish` com routing key, exchange e
  properties corretas; confirm `True` → sucesso, `False`/exceção → retry e
  depois descarte.
- `consumer`/`app`: `on_message` enfileira mensagens válidas e descarta
  inválidas; shutdown fecha publisher e consumer.

Smoke manual documentado: subir a stack, publicar `mosquitto_pub` no tópico,
verificar a mensagem no exchange via `rabbitmqadmin`/management UI, e confirmar
que um binding de teste recebe o payload.

## Documentação

- Corrigir `docs/comunicacao_entre_servicos.md` (seção 5) para refletir o novo
  fluxo MQTT → RabbitMQ e remover as referências a `mqtt_consumer` no
  `client_agent` e a `INGEST_URL`.
- Atualizar `docs/middleware/README.md` e `middleware/services/routing`
  (descrição do serviço).
- Atualizar `SPRINTS_BACKLOG.md`/`PROGRESS.md` conforme o item relacionado.

## Validação

- `pytest` verde no pacote `middleware/services/routing`.
- `black --check`, `isort --check`, `mypy`, `flake8` sem erros.
- Stack sobe com `rabbitmq` healthy; `routing` conecta em ambos os brokers.
- `mosquitto_pub` de um payload ChirpStack válido resulta em uma mensagem no
  exchange com a routing key esperada.
- `.github/workflows/middleware-ci.yml` continua verde para
  `services/routing`.

## Riscos e mitigações

- **Perda de telemetria na transição:** enquanto os consumidores não existirem,
  as mensagens publicadas não têm destino persistido. Mitigação: declarar
  exchange durável e documentar o consumo como próximo spec; opcionalmente
  criar uma fila de auditoria temporária com binding `#` durante a validação.
- **rabbitpy sem maturidade de ecossistema (vs pika):** API menor e menos
  exemplos. Mitigação: confirmar `enable_publisher_confirms()` e properties na
  implementação; cobrir com testes unitários de publisher.
- **Thread-safety do rabbitpy:** avança como thread-safe, mas a conexão/canal
  fica em uma única thread publisher, evitando compartilhamento.
- **`device_routes` vira código órfão:** não removida neste escopo; deve ser
  tratada no spec de migração dos consumidores.
- **Mismatch de formato da routing key:** tópico usa `/` e a routing key usa
  `.`; erro de parsing descarta a mensagem. Mitigação: testar a conversão.

## Commits

1. `refactor(middleware): remove roteamento HTTP do consumer e adiciona publisher RabbitMQ`
2. `feat(middleware): valida integridade e publica envelope no exchange`
3. `test(middleware): cobre validação, envelope e publisher`
4. `build(deploy): adiciona RabbitMQ à stack e ajusta routing`
5. `docs(middleware): atualiza fluxo de ingestão no RabbitMQ`
