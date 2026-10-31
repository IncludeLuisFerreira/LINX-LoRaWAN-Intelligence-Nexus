# Contratos gRPC

Os contratos gRPC da plataforma ficam em `proto/` e os stubs Python são
versionados no pacote compartilhado `linx_shared.grpc`.

## `proto/linx_agent.proto`

Contrato compartilhado entre o **Linx Core** (servidor) e o **Client Agent
API** (middleware compartilhado). Define o serviço `AgentBridge`, que sustenta
toda a comunicação gRPC entre os serviços da plataforma.

Definido na issue [#19](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/19).
A geração dos stubs Python é feita na issue #20.

## Serviço `AgentBridge`

| RPC              | Request        | Response     | Direção                         | Uso (Sprint) |
| ---------------- | -------------- | ------------ | ------------------------------- | ------------ |
| `GetAppConfig`   | `AppId`        | `AppConfig`  | Client Agent → SaaS             | Config do tenant sob demanda (S2) |
| `IngestTelemetry`| `TelemetryEvent` | `Ack`      | SaaS → Client Agent             | Ingestão de telemetria (S2/S3) |
| `SyncRule`       | `Rule`         | `Ack`        | SaaS → Client Agent             | Replicar regra ao tenant (S6) |
| `ReportViolation`| `Violation`    | `Ack`        | Client Agent → SaaS             | Notificar violação de regra (S6) |

> **Nota sobre direção (bidirecional):** o contrato é único, mas cada lado
> expõe um servidor gRPC conforme o RPC. O **Linx Core** hospeda
> `GetAppConfig` e `ReportViolation`; o **Client Agent API** (middleware
> compartilhado) hospeda `SyncRule` e `IngestTelemetry`. A persistência de
> telemetria é feita pelo serviço `telemetry_consumer`, que consome o
> exchange RabbitMQ `linx.telemetry` e grava no TimescaleDB do tenant.
> O RPC `IngestTelemetry` cobre o caminho de roteamento do SaaS (Sprint 3), a
> confirmar na implementação.

> **Segurança:** `AppConfig.db_password` trafega em texto plano no gRPC. O
> canal deve usar TLS/mTLS (Sprint 5) antes de qualquer deploy fora de dev.

## Mensagens

### `AppId`

| Campo    | Tipo   | # | Descrição                       |
| -------- | ------ | - | ------------------------------- |
| `app_id` | string | 1 | Identificador UUID da aplicação |

### `AppConfig`

| Campo         | Tipo   | # | Descrição                                |
| ------------- | ------ | - | ---------------------------------------- |
| `app_id`      | string | 1 | Identificador UUID da aplicação          |
| `db_host`     | string | 2 | Host do TimescaleDB do tenant            |
| `db_port`     | uint32 | 3 | Porta do TimescaleDB                     |
| `db_name`     | string | 4 | Nome do banco do tenant                  |
| `db_user`     | string | 5 | Usuário do banco                         |
| `db_password` | string | 6 | Senha do banco                           |
| `mqtt_topic`  | string | 7 | Tópico MQTT de assinatura (`application/<app_id>/device/+/event/up`) |

### `TelemetryEvent`

| Campo       | Tipo                     | # | Descrição                                  |
| ----------- | ------------------------ | - | ------------------------------------------ |
| `dev_eui`   | string                   | 1 | DevEUI do dispositivo (TEXT no schema)     |
| `timestamp` | `google.protobuf.Timestamp` | 2 | Instante do uplink (TIMESTAMPTZ)         |
| `payload`   | string                   | 3 | Payload JSON (JSONB no schema)             |
| `rssi`      | int32                    | 4 | RSSI (INT no schema)                       |
| `snr`       | double                   | 5 | SNR (FLOAT/float8 no schema)               |
| `f_cnt`     | uint32                   | 6 | Frame counter (opcional, ordenação/dedup)  |

### `Rule`

| Campo          | Tipo   | # | Descrição                                        |
| -------------- | ------ | - | ------------------------------------------------ |
| `id`           | string | 1 | Identificador da regra                           |
| `sensor_field` | string | 2 | Campo do sensor (`temperature`, `ldr_value`, …)  |
| `operator`     | string | 3 | Operador (`>`, `<`, `==`, `!=`)                  |
| `threshold`    | double | 4 | Limiar da comparação                             |
| `action_type`  | string | 5 | Ação (`downlink`, `telegram`, `email`)           |

### `Violation`

| Campo     | Tipo   | # | Descrição                            |
| --------- | ------ | - | ------------------------------------ |
| `rule_id` | string | 1 | Regra violada                        |
| `dev_eui` | string | 2 | Dispositivo que disparou a violação  |
| `message` | string | 3 | Descrição da violação                |

### `Ack`

| Campo   | Tipo   | # | Descrição                                     |
| ------- | ------ | - | --------------------------------------------- |
| `ok`    | bool   | 1 | `true` se a operação foi aceita               |
| `error` | string | 2 | Mensagem de erro (vazia em caso de sucesso)   |

## `proto/linx_docker_provisioner.proto`

Contrato interno entre o `jobs_worker` (cliente gRPC) e o
`docker_provisioner` (servidor). No fluxo assíncrono, o `identity_api`
valida tenant/application no Postgres e enfileira um job; quem chama este RPC
enviando apenas o `app_id` é o `jobs_worker`. O provisioner concentra a
política de imagem, porta, rede e variáveis de ambiente.

| Item | Valor |
| ---- | ----- |
| Serviço | `DockerProvisioner` |
| RPC | `ProvisionApplication` |
| Porta | `50052` (rede interna do Compose) |
| Autenticação | metadado `authorization: Bearer <SERVICE_TOKEN>` |
| Request | `ProvisionApplicationRequest { string app_id = 1; }` |
| Response | `container_id`, `port`, `network`, `image`, `status`, `created`, `mqtt_topic` |

> `DB_PASSWORD` é gerado pelo provisioner e injetado apenas no container do
> tenant; ele não trafega no gRPC nem é retornado ao `identity_api`.

## Como compilar / verificar

```bash
protoc --descriptor_set_out=/dev/null --proto_path=proto proto/linx_agent.proto
protoc --descriptor_set_out=/dev/null --proto_path=proto \
  proto/linx_docker_provisioner.proto
```

## Gerar stubs Python

Os stubs são versionados em um único lugar:
`linx_core/shared/src/linx_shared/grpc/` (pacote `linx_shared`). O
`client_agent` resolve `linx_agent_pb2` por esse pacote (path dependency),
como o serviço `routing`; não há mais cópia sob `middleware/` (#215). Para
regenerar:

```bash
bash scripts/gen_proto.sh
```

O script usa `grpc_tools.protoc` para os dois contratos e corrige os imports
absolutos gerados para relativos (`from . import <proto>_pb2`), necessário
dentro do pacote. Requer `grpcio-tools` instalado em `linx_core/shared` (dev
dependency). O CI regenera os stubs e falha se divergirem do versionado
(drift gate).
