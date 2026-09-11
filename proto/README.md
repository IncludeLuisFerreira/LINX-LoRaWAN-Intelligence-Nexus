# Contrato gRPC — `proto/saas_agent.proto`

Contrato compartilhado entre o **SaaS Backend** (servidor) e o **Client Agent**
(cliente). Define o serviço `AgentBridge`, que sustenta toda a comunicação gRPC
entre os serviços da plataforma.

Definido na issue [#19](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/19).
A geração dos stubs Python é feita na issue #20.

## Serviço `AgentBridge`

| RPC              | Request        | Response     | Direção                         | Uso (Sprint) |
| ---------------- | -------------- | ------------ | ------------------------------- | ------------ |
| `GetAppConfig`   | `AppId`        | `AppConfig`  | Client Agent → SaaS             | Config do tenant no startup (S2) |
| `IngestTelemetry`| `TelemetryEvent` | `Ack`      | SaaS → Client Agent             | Ingestão de telemetria (S2/S3) |
| `SyncRule`       | `Rule`         | `Ack`        | SaaS → Client Agent             | Replicar regra ao tenant (S6) |
| `ReportViolation`| `Violation`    | `Ack`        | Client Agent → SaaS             | Notificar violação de regra (S6) |

> **Nota sobre direção (bidirecional):** o contrato é único, mas cada lado
> expõe um servidor gRPC conforme o RPC. O **SaaS Backend** hospeda
> `GetAppConfig` e `ReportViolation`; o **Client Agent** hospeda `SyncRule` e
> `IngestTelemetry`. A ingestão de telemetria hoje flui via **MQTT → Client
> Agent** (Sprint 2); o RPC `IngestTelemetry` cobre o caminho de roteamento do
> SaaS (Sprint 3), a confirmar na implementação.

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
| `mqtt_topic`  | string | 7 | Tópico MQTT de assinatura (`application/+/device/+/event/up`) |

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

## Como compilar / verificar

```bash
protoc --descriptor_set_out=/dev/null --proto_path=proto proto/saas_agent.proto
```

## Gerar stubs Python (issue #20)

```bash
python -m grpc_tools.protoc \
  -I proto \
  --python_out=saas_backend/src/linx/grpc \
  --grpc_python_out=saas_backend/src/linx/grpc \
  proto/saas_agent.proto
```
