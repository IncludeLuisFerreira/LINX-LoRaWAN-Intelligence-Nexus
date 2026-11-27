# LINX Messaging — Design

**Issue epic:** consolidação da mensageria (follow-ups #233, #234, #254; infraestrutura e biblioteca).
**Data:** 2026-11-27
**Status:** proposta para aprovação.

## Intenção

Consolidar a mensageria AMQP do LINX em **um único RabbitMQ**, com **uma única biblioteca (Pika 1.5.0, API `pika.Connection`)**, atrás de uma porta interna (`linx_shared.messaging`). O resultado deve ser entendível, sem hardcode de topologia, resiliente a falhas de broker e de processamento, e coberto por testes reais com cobertura ≥ 70% por pacote.

O sistema tem dois domínios de mensageria:

- **Jobs internos** (`linx_shared.jobs`, `jobs_worker`, `jobs_status_worker`), hoje em `pika.BlockingConnection`, com topologia fixa para `provisioning.application` e sem DLQ na fila de status.
- **Telemetria** (`middleware/services/routing`, `client/services/telemetry_consumer`), hoje em `rabbitpy`, com topologia por tenant, retry, DLQ e reconexão.

Hoje convivem duas bibliotecas, três brokers em dev/test e implementações de resiliência desiguais. A telemetria é a referência de resiliência; os jobs são o ponto frágil.

## Por que agora

- A topologia interna não suporta um segundo tipo de job (#233): eventos `.succeeded`/`.failed`/`.dead` de outro tipo caem em `UnroutableError` e o job trava em `RUNNING`.
- A quarentena da outbox deixa jobs `PENDING` órfãos (#234).
- O consumer interno descarta mensagem inválida sem DLQ e faz `nack(requeue=True)` ilimitado em erro de processamento (`linx_shared/jobs/consumer.py:53-67`).
- `pika.BlockingConnection` está deprecado e será removido no Pika 2.0; o repo depende dele em todo o domínio de jobs.
- O CI de jobs não sobe RabbitMQ (`backend-ci.yml` só tem Postgres), então rota real nunca é testada.

## Objetivos

1. Um RabbitMQ único no stack base (`infra/docker-compose.base.yml`), compartilhado por jobs e telemetria.
2. `linx_shared.messaging` como única porta de entrada para publicar, consumir e declarar topologia.
3. Pika 1.5.0 com `pika.Connection` como biblioteca/API oficial; nenhuma outra biblioteca AMQP ao final.
4. Topologia declarativa, sem nomes de fila/exchange hardcoded fora dela (#233 resolvido).
5. Política única de falha: publisher confirms, ACK manual, retry limitado com backoff, DLQ, poison message (#234 incluído).
6. Reconexão/recovery de canais e consumidores separados da política de processamento.
7. Testes de integração com RabbitMQ real no CI e cobertura ≥ 70%.
8. Caminho preparado para isolamento por vhost (B), mantendo ACL hoje (A).

## Não-objetivos

- Migrar MQTT/Mosquitto (`#81`, `#105`, `#108`, `#110`, `#112`, `#125`, `#255`). É outro broker.
- Substituir RabbitMQ por Kafka/Redis Streams.
- Alta disponibilidade/cluster de RabbitMQ ou multi-região.
- Isolamento por vhost agora (vira follow-up com o `TenantProvisioner`).
- Unificar todos os compose em um único arquivo (Arquitetura B). O merge de stacks fica para depois, se ainda fizer sentido.
- Métricas Prometheus completas (issue #118 segue fora): nesta entrega, logs estruturados + health + contadores internos.
- **Kubernetes.** `infra/kubernetes/base/rabbitmq.yaml` fica fora desta entrega por decisão explícita. O épico garante um broker nos stacks Docker (dev/deploy/CI). A convergência do manifesto k8s vira issue de follow-up, com o mesmo contrato de topologia e env.

## Requisitos de produto (fora do escopo desta entrega, mas registrados)

O código vai virar produto real. Este épico entrega mensageria correta e resiliente a falhas de aplicação/broker, mas **não** entrega tudo que produção exige. Ficam como issues de follow-up obrigatórias, sem serem silenciadas:

- **HA do broker:** um RabbitMQ único em compose/k8s é ponto único de falha. Produção exige cluster (quorum queues) ou broker gerenciado, com política de réplica.
- **TLS/AMQP seguro** (issue #78) e rotação de credenciais; hoje o management e o AMQP ficam em loopback no deploy.
- **Observabilidade de produção:** métricas Prometheus (#118), alarmes de DLQ/quarentena/reconexão e dashboards.
- **DR/backup:** backup de definitions e runbook de recuperação (`docs/backend/DR.md`, #128).
- **K8s:** convergir o broker do laboratório para o broker único do produto.
- **Contrato de entrega documentado:** at-least-once, idempotência por consumidor, DLQ operável e replay procedure.

Estes itens não bloqueiam as fatias 0–6, mas devem existir como issues antes de qualquer go-live.

## Anti-objetivos

- Terminar a migração com duas bibliotecas AMQP no repositório.
- Publicar sem publisher confirm no caminho de jobs.
- Dar ACK antes do processamento ou antes da confirmação da DLQ.
- `nack(requeue=True)` sem limite.
- Nome de fila/exchange/routing key fora de `topology.py`.
- Subir mais de um RabbitMQ em qualquer compose.
- Mudar o isolamento de tenants nesta entrega.

## Restrições

- Python `>=3.12,<4.0` no CI (local: 3.14.10); Pika 1.5.0 exige `>=3.7`.
- Pika 1.5.0 é recente (publicado em 2026-11-17); `pika.Connection` não existe em 1.4.4 (verificado).
- `pika.Connection.basic_publish` é **fire-and-forget** e **não levanta** `UnroutableError`/`NackError`; confirmações chegam por callback (`confirm_delivery(ack_nack_callback)` + `on_publish` tag), e retorno de mensagem não roteada por `add_on_return_callback`.
- `pika.Connection` não tem `process_data_events`, `start_consuming` nem `sleep`; callbacks de entrega rodam em thread de trabalho por canal e o processo consumidor bloqueia em `threading.Event().wait()`.
- `pika.Connection` não reconecta sozinho; `on_close_callback` dispara e o manager precisa recriar conexão, canais, topologia e consumidores.
- `pika.Connection` limita a fila de callbacks (`work_queue_maxsize`, `work_queue_put_timeout`, `shutdown_drain_timeout`); consumer lento pode bloquear o IOLoop.
- `AGENTS.md`: uma branch/PR por issue, commits em português com `(#N)`, `git add` explícito, sem tocar trabalho de outro agente.
- A branch `feat/jobs-status-worker` (#232) está aberta e altera os chamadores de `declare_topology`. #232 é pré-requisito da fatia 2.

## Abordagens consideradas

### A — Broker base + porta `linx_shared.messaging` + migração incremental (escolhida para infraestrutura/abstração)

Broker único no stack base; módulo de mensageria com portas e adaptador; migração strangler. Cada fatia é mergeável e demonstrável.

### B — Plataforma única em um compose com profiles

Um compose só, com todos os serviços e um broker. Ótimo DX, mas PR gigante, conflito com trabalho em andamento e nenhum ganho direto de resiliência. Rejeitada para esta entrega.

### C — Pika 1.5.0 com `pika.Connection` como biblioteca oficial (escolhida para biblioteca)

Elimina `rabbitpy` e evita a remoção futura do `BlockingConnection` no Pika 2.0. Custo: reescrever publisher/consumer de jobs e validar a nova API.

### A + C — combinação escolhida

Infraestrutura/abstração de A, biblioteca/API de C. Rejeitamos padronizar em `rabbitpy` porque ele é usado em 2 serviços contra 3 pacotes de jobs + shared, e porque Pika é mantido pelo time do RabbitMQ. Rejeitamos manter `BlockingConnection` porque ele será removido.

## Decisões de implementação

### Broker único

- `infra/docker-compose.base.yml` passa a declarar `rabbitmq` (imagem `rabbitmq:3-management`), volume próprio, healthcheck, portas publicadas apenas no loopback, na rede `linx-network`.
- Remover o serviço `rabbitmq` de:
  - `linx_core/docker-compose.yml`
  - `deploy/docker-compose.yml`
  - `tests/integration/telemetry/docker-compose.override.yml`
- Todos os serviços que falam AMQP entram na rede `linx-network` e usam o host `rabbitmq`.
- `make up-core` e `make up-deploy` passam a exigir o broker no ar. O Makefile deve falhar com mensagem clara se `rabbitmq` não estiver acessível, em vez de subir um broker implícito.
- O CI usa **service container** de RabbitMQ por workflow (não compose): `backend-ci.yml` ganha o serviço; `telemetry-consumer-ci.yml` já tem e permanece.
- Nenhum compose pode voltar a declarar um segundo `rabbitmq`; isso é verificado por teste/checagem de CI (grep nos compose).

### Módulo `linx_shared.messaging`

Estrutura e responsabilidades (sem dependência de Pika fora de `pika_adapter.py`/`connection_manager.py`):

- `ports.py` — protocolos:
  - `Publisher.publish(exchange, routing_key, payload, message_id, mandatory=True) -> PublishResult`
  - `Consumer.start(queue, handler, prefetch, stop_event)` / `stop()`
  - `TopologyBuilder.declare_topology(channel, topology)`
  - `HealthProbe.check() -> bool`
- `topology.py` — modelo declarativo (dataclasses):
  - `ExchangeSpec(name, type, durable)`
  - `QueueSpec(name, durable, arguments)`
  - `BindingSpec(queue, exchange, routing_key)`
  - `JobTypeTopology(job_type, command_queue, dlq, dead_routing_key, status_binding)`
  - `Topology(exchanges, queues, bindings)` + funções puras para montar a topologia de jobs e a de telemetria.
  - Regra: nenhum nome de exchange/fila/routing key fora deste módulo e de `constants.py` (que passa a conter apenas nomes neutros e o registro de tipos).
- `policy.py` — decisão de resultado por mensagem:
  - `ProcessOutcome.ACK` / `RETRY` / `DEAD_LETTER`.
  - Limite de tentativas lido de `x-death` (header do RabbitMQ) ou contador explícito; ao exceder, DLQ.
  - Mensagem inválida/venenosa → DLQ sempre (nunca descarte silencioso).
  - Backoff de retry dentro do processo é responsabilidade do domínio (jobs já tem `RETRY_DELAYS_SECONDS`; telemetria já tem retry próprio). A política compartilhada decide apenas ACK/retry-broker/DLQ.
- `connection_manager.py` — dono do ciclo de vida:
  - Cria `pika.Connection` com `on_open_error_callback` e `on_close_callback`.
  - Reconexão com backoff exponencial + jitter, tentativas limitadas; health expõe estado.
  - Após reconectar: redeclara topologia idempotente e recria canais/consumidores.
  - Reconexão/recovery **não** decide ACK/DLQ; isso é da política.
- `pika_adapter.py` — implementação:
  - `PikaPublisher`, `PikaConsumer`, `PikaTopologyBuilder`, `PikaHealthProbe`.
  - Publisher confirmado (ver abaixo).
  - Consumer com `basic_qos(prefetch)`, `basic_consume(auto_ack=False)` e handler traduzindo `ProcessOutcome` para `basic_ack`/`basic_nack`.

`linx_shared/jobs/*` continua existindo como domínio (envelope, outbox, repository, handler registry), mas publisher/consumer/topologia passam a usar `linx_shared.messaging`.

### Publicação com confirmação (ponto crítico)

O contrato atual da outbox depende de a publicação falhar de forma observável (`UnroutableError`) para incrementar tentativas e quarentenar. Com `pika.Connection` isso não existe como exceção. O adaptador deve reconstruir o contrato:

1. `channel.confirm_delivery(ack_nack_callback)` na criação do canal de publicação.
2. `channel.add_on_return_callback(...)` para `mandatory=True`.
3. Cada `publish()` cria um `Future`; `on_publish(tag)` associa tag→future; o callback de confirm resolve com ACK/NACK; o callback de return marca "unroutable".
4. `publish()` bloqueia até ACK (sem return) ou NACK/return/timeout, e então retorna `PublishResult` ou levanta erro equivalente ao atual.
5. Timeout de confirmação é configurável e menor que o heartbeat efetivo.

**Gate:** esse mapeamento é a pergunta central do spike (fatia 0). Se não for possível garantir associação tag→future sem corrida, o fallback precisa de decisão explícita: (a) usar `SelectConnection` com IOLoop próprio; (b) manter `BlockingConnection` isolado dentro do adaptador, apenas para publicação, com aprovação registrada; (c) tornar a outbox assíncrona (marcar publicado só no callback). Nenhum fallback entra sem registro no ADR.

### Consumo, ACK e poison

- `auto_ack=False` sempre; ACK só após processamento concluído.
- `InvalidMessageError`/payload inválido → publish confirmado no DLX, depois ACK. Nunca descarte silencioso.
- Erro transitório de infraestrutura (DB indisponível) → mensagem fica **sem ACK** e o consumer tenta novamente em processo, com backoff limitado; ao esgotar, DLX com publish confirmado e ACK.
- Erro de domínio tratado (retry já agendado no domínio) → ACK. O broker não duplica o retry que a outbox já controla.
- Fila de status ganha DLX/DLQ (`linx.jobs.status.dlq`), hoje ausente.
- Erro permanente de domínio → DLX direto.
- Idempotência: status de jobs já é idempotente (`apply_status_event`); telemetria já usa `ON CONFLICT (app_id, dev_eui, time, event_type) DO NOTHING` (`telemetry_consumer/db.py:202`). Manter e testar.

### Decisões do builder check

Estas decisões fecham lacunas apontadas na revisão independente:

1. **Retry não é contado pelo broker.** `x-death` só existe em dead-letter e `nack(requeue=True)` não incrementa contador em fila clássica. Portanto: jobs usam o retry do domínio (outbox + `job.max_attempts`, já existente); telemetria mantém retry em processo com teto total curto (≤ ~10 s) e DLQ ao fim. Não há fila de retry nem quorum queue nesta entrega. O `ProcessOutcome.RETRY` do `policy.py` existe apenas para falha de infraestrutura **antes** de o domínio gravar estado, com limite em processo; nunca para erro de handler que o domínio já tratou.
2. **DLQ por publicação confirmada, não por `nack(requeue=False)` puro.** O `policy` publica no DLX com confirm e só então dá ACK. Broker DLX continua declarado como defesa em profundidade (consumer que morre no meio), mas o caminho normal é confirmado. Duplicatas são possíveis (at-least-once) e cobertas pela idempotência.
3. **`.dead` continua comando (túmulo), não status.** Não criar `JobStatus.DEAD`. Falha terminal permanece `FAILED` com `error.code`; broker-side dead-letter chama um hook que grava `FAILED` com código `dead_lettered`; quarentena de comando na outbox grava `FAILED` com `command_publish_failed` (fecha #234); quarentena de evento de status dispara reconciliação/alerta. O contrato `FAILED` + `error.code` é documentado e testado; mudar para status `DEAD` exigiria schema/API e não é feito agora.
4. **Schema da outbox não muda neste épico.** `exchange`/`routing_key` continuam persistidos; quem os gera passa a ser `topology.py` (`command_route`, `event_route`). CI proíbe literais de exchange/fila/routing key fora dos módulos de mensageria. Normalizar o schema para `job_type` + tipo de evento é follow-up.
5. **Sem binding catch-all.** O registro de tipos é compartilhado; criação de job valida o tipo; workers validam a cobertura do registro no startup; quarentena/`UnroutableError` gera alerta. Um tipo desconhecido falha cedo em vez de cair na fila de status.
6. **Compatibilidade de nomes.** `provisioning.application` mantém a fila `linx.jobs.provisioning`; tipos novos usam `linx.jobs.<tipo>`. Nada é renomeado só por estética.
7. **Kubernetes fora do escopo.** Registrado nos não-objetivos e como follow-up obrigatório de produto.

### Topologia declarativa (resolve #233)

- Exchanges globais: `linx.jobs`, `linx.jobs.events`, `linx.jobs.dlx`.
- Por tipo de job (`JobTypeTopology`):
  - fila de comando `linx.jobs.<tipo>`
  - DLQ `linx.jobs.<tipo>.dlq`
  - binding de comando `<tipo>.requested`
  - binding da DLQ `<tipo>.dead`
  - binding da fila de status única `linx.jobs.status` com `<tipo>.#` (uma binding por tipo, não catch-all `#`)
- A fila de status é única e declara uma binding por tipo suportado. Isso evita mascarar typo de routing key e atende ao critério da #233.
- Teste de roteabilidade cobre todos os eventos de um segundo tipo sintético (`.requested`, `.started`, `.succeeded`, `.failed`, `.retry`, `.dead`).

### Shutdown controlado

- `SIGTERM`/`SIGINT` → sinaliza `stop_event`, `basic_cancel` dos consumidores, aguarda in-flight até timeout, fecha conexão (`shutdown_drain_timeout`).
- Nenhum ACK depois do fechamento; mensagem não confirmada volta a ser entregue.

### `TenantProvisioner` e caminho para B

- Extrair a lógica de provisionamento de tenant em `identity_api` para uma interface `TenantProvisioner`:
  - `AclTenantProvisioner` — comportamento atual: usuário `tenant.{app_id}` + ACL regex no vhost `/` (`linx_shared/core/rabbitmq.py:23-30`).
  - `VhostTenantProvisioner` — implementação futura (vhost por tenant), não nesta entrega.
- Seleção por configuração (`RABBITMQ_ISOLATION_MODE=acl|vhost`), default `acl`.
- `TopologyBuilder` recebe o vhost como parâmetro (hoje `/`).
- ADR registra gatilhos para migrar a B (ex.: requisito de compliance, número de tenants, incidente de ACL).

### Padronização de configuração

- Nomes canônicos de env: `RABBITMQ_AMQP_URL` (AMQP) e `RABBITMQ_MANAGEMENT_URL` (HTTP). `RABBIT_URL` (telemetria) permanece aceito como alias depreciado nesta entrega, para não quebrar deploys; documentar a depreciação.
- Remover env fantasma `RABBIT_EXCHANGE` (citado em `.env.example` e ignorado pelo consumer).
- Defaults de credencial fraca continuam proibidos; validação no startup (`#210` já fechado, não regredir).

## Requisitos de confiabilidade e onde são atendidos

| Requisito | Onde |
|---|---|
| Publisher confirms | `pika_adapter.PikaPublisher` + spike |
| ACK manual | `pika_adapter.PikaConsumer` |
| Retry limitado + backoff | `policy.py` + domínio (jobs/telemetria) |
| DLQ por fila pertinente | `topology.py` + declaração das filas |
| Poison message | `policy.py` |
| Reconexão do broker | `connection_manager.py` |
| Recuperação de canais/consumidores | `connection_manager.py` |
| Idempotência | `apply_status_event`; `ON CONFLICT` da telemetria |
| Outbox transacional (#234) | `outbox.py` + `PikaPublisher` |
| Shutdown controlado | `connection_manager.py` + entrypoints |

## Fatia 0 — Spike Pika 1.5.0 (gate)

Timebox: 1 dia. Código descartável em branch própria, sem merge.

Perguntas a responder com evidência:

1. Publisher confirmado: é possível mapear `on_publish` tag → future e obter ACK/NACK/return sem corrida, com timeout? Quais erros são observáveis?
2. `mandatory=True` + `add_on_return_callback` detecta mensagem não roteada de forma confiável?
3. Consumo com ACK manual em thread de trabalho + `stop_event` encerra sem perder mensagem?
4. `on_close_callback` permite reconstruir conexão, canais, topologia e consumidores sem vazar threads?
5. `basic_nack` para DLQ funciona com fila declarada com DLX?
6. Comportamento de `work_queue_maxsize`/`shutdown_drain_timeout` sob consumer lento.

Saída: ADR curto (`docs/superpowers/specs/2026-11-27-pika-connection-adr.md`) com decisão "segue com `pika.Connection`" ou fallback registrado, mais um exemplo executável do publisher confirmado.

## Estratégia de migração (fatias)

| Fatia | Entrega | Critério de aceite |
|---|---|---|
| 0 | Spike + ADR | Perguntas acima respondidas com código rodando |
| 1 | Broker único no base; stacks sem broker próprio; `linx-network` | `make up-base` + `up-core` + `up-deploy` usam o mesmo broker; grep de CI garante um só `rabbitmq` |
| 2 | `topology.py` + #233 | Segundo tipo publica todos os eventos e é roteado (teste com broker real ou fake que simula topic) |
| 3 | `policy.py` + DLQ de status + #234 | Poison e retry esgotado vão para DLQ; job com comando quarentenado não fica `PENDING` para sempre |
| 4 | Jobs no `pika_adapter`; remover `pika.BlockingConnection` e `rabbitpy` | Nenhum import de `BlockingConnection`/`rabbitpy` no código de produção |
| 5 | Telemetria na topologia comum; CI com RabbitMQ real; #254 | Testes de rota/isolamento rodam sem skip; script de isolamento no CI |
| 6 | Observabilidade, runbook e fechamento | Contadores de DLQ/reconexão/quarentena expostos em health/log; docs atualizadas |

Cada fatia: branch própria a partir de `develop` atualizado, PR com a issue correspondente, testes e demo. **Não** fazer refatoração completa em um PR.

Dependências: #232 antes da fatia 2. Fatias 1 e 0 podem começar em paralelo.

### Cutover e perda aceitável (decidido)

**Decisão:** o produto está em MVP, sem tráfego ou dado crítico em fila hoje. A virada é pré-lançamento e **pode recriar a topologia** no broker único.

Consequências:

- Filas antigas podem ser deletadas/redeclaradas; nada de valor é perdido.
- Não haverá drenagem nem dual-consume. O runbook de cutover apenas documenta: parar consumers → deletar filas antigas no broker antigo → subir broker único → redeclarar topologia → subir consumers.
- Adicionar `x-dead-letter-exchange` a `linx.jobs.status` (que hoje daria `406 PRECONDITION_FAILED` em fila existente) é seguro no cutover.
- `WORKER_QUEUE`/`STATUS_QUEUE` permanecem como overrides, depreciados, até segunda ordem.
- **Gate de go-live:** antes de qualquer lançamento real, os itens da seção "Requisitos de produto" precisam de issue e execução. A partir do go-live, cutovers passam a exigir drenagem documentada.

## Testes e CI

- Unitários com fakes de porta (sem Pika) para `policy.py`, `topology.py` e domínio.
- Integração com RabbitMQ real:
  - rota de cada evento por tipo de job;
  - malformed → DLQ;
  - retry esgotado → DLQ;
  - reconnect: derrubar a conexão e verificar que o manager recria consumidor;
  - publish confirmado: unroutable não marca outbox como publicado;
  - isolamento multi-tenant de telemetria (A) sem skip.
- `backend-ci.yml` ganha service `rabbitmq:3-management` e os testes de integração entram na matriz.
- Cobertura ≥ 70% por pacote (`--cov-fail-under=70`) mantida; novos módulos precisam de testes que sustentem o número.
- Checagem estática: nenhum `rabbitmq` duplicado nos compose; nenhum nome de fila hardcoded fora de `topology.py`/`constants.py`.

## Validação final

1. `pytest` por pacote com cobertura ≥ 70%.
2. `black --check`, `isort --check-only`, `flake8`, `mypy` limpos.
3. Smoke jobs: `POST /jobs` → outbox → broker → worker → status aplicado.
4. Smoke telemetria: MQTT → routing → broker → telemetry_consumer → REST/WS.
5. Drill de DLQ: mensagem venenosa e retry esgotado terminam na DLQ correta.
6. Drill de broker: parar/religar o RabbitMQ e verificar reconexão sem perda de mensagem.
7. Verificar no management UI que existe **um** broker e que cada fila tem DLQ quando pertinente.

## Riscos

| Risco | Mitigação |
|---|---|
| Pika 1.5.0 é novo (2026-11-17) e `pika.Connection` é API nova | Pin exato, spike gate, integração com broker real |
| Publisher confirmado não reproduz a semântica de exceção | Future tag→confirm no adaptador; fallback registrado no ADR |
| Consumer lento bloqueia IOLoop (work queue) | Ajustar `work_queue_maxsize`/timeouts; prefetch e threads pequenas; teste de carga básico |
| Mudança de dependência do compose base quebra DX | Makefile com pré-checagem e mensagem clara; README atualizado |
| Conflito com #232 nos chamadores de `declare_topology` | #232 primeiro; fatia 2 rebaseada |
| Escopo crescer para merge de stacks (B) | Não-objetivo explícito; fica para follow-up |
| Isolamento por ACL ser mal configurado | Testes de isolamento sem skip; `TenantProvisioner` testado |

## O que fica para o builder

- Definir os valores concretos de retry (tentativas, backoff) e o teto total do retry de infraestrutura, por serviço.
- Definir se `infra/docker-compose.yml` inclui `docker-compose.base.yml` via `include:` ou se o Makefile orquestra os dois.
- Escolher o timeout de confirmação e o limite de `work_queue_maxsize` com base no spike.
- Definir o formato exato do `PublishResult` e a tradução para os erros atuais da outbox.
- Decidir a forma de exposição de métricas sem Prometheus (health JSON, contadores em log ou endpoint dedicado).
- Detalhar o contrato do `TenantProvisioner` e os testes de compatibilidade ACL→vhost.
- Definir o hook `on_dead` (assinatura e onde é ligado no jobs wiring) e a reconciliação de eventos de status quarentenados.
- Granularidade dos testes de integração por fatia (o que roda em cada PR vs. nightly).
- Executar o cutover conforme a decisão de perda aceitável acima.
