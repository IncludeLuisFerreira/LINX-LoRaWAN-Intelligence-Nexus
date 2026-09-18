# Design: tenant_app busca GetAppConfig e loga "AppConfig received" (issue #38)

**Data:** 2026-09-17
**Issue:** [#38](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/38)
**Sprint:** 2
**Escopo:** `tenant_app_template` conecta no SaaS Backend via gRPC no startup, chama `GetAppConfig(APP_ID)` e loga `AppConfig received` (prova de comunicação da S2).
**Relacionado:** #19/#20 (contrato e stubs gRPC), #34 (Model A — `client_agent_api` como middleware), #36 (pipeline de ingestão), #37 (deploy — fora de escopo).

## Contexto

A issue #38 pede o "log estruturado do `AppConfig` recebido via gRPC no startup",
como prova de comunicação exigida nos critérios de aceite da S2 ("Log do Client
Agent mostrando `AppConfig` recebido do SaaS via gRPC").

O corpo original da issue aponta `client_agent_api/grpc_client.py` como o local
da chamada. Porém, no Model A o `client_agent_api` é o **middleware compartilhado**
(multi-tenant, sem `app_id` próprio — há até um teste `test_settings_have_no_app_id`
reforçando isso), enquanto o **`tenant_app_template`** é o contêiner isolado por
aplicação e já carrega um `APP_ID` específico (`.env.example`, `docker-compose.yml`).

Decisão acordada: quem busca o `GetAppConfig` é o **`tenant_app_template`**, que
tem um `app_id` definido via env. No startup ele conecta no SaaS, busca a config
e loga `AppConfig received` — sem usar a config para montar o pool (isso fica
para a #35). O pool do TimescaleDB continua vindo das envs `DB_*`.

## Objetivo

- No startup, o `tenant_app` loga `AppConfig received` com `app_id`, `db_host`,
  `db_port` e `mqtt_topic`, visível no stdout/`docker logs`.
- Falha na chamada gRPC não derruba o serviço (degradação graciosa).
- `db_user`/`db_password` jamais são logados.

## Não-objetivos

- Usar o `AppConfig` recebido para configurar a conexão do TimescaleDB (#35).
- Deploy do tenant em EC2 (#37).
- Roteamento por `app_id` no middleware (#47).
- Cache/uso on-demand da config (a S2 exige apenas a prova de comunicação no startup).

## Arquitetura e fluxo

```
tenant_app (FastAPI, startup/lifespan)
  └─ SaasConfigClient.get_app_config(APP_ID)   [grpc, porta 50051 do SaaS]
       ├─ GetAppConfig(AppId{app_id}) → AppConfig{db_host, db_port, mqtt_topic, ...}
       ├─ logger.info("AppConfig received app_id=... db_host=... db_port=... mqtt_topic=...")
       └─ retorna AppConfig (não usado além do log nesta issue)
  └─ create_db_pool(...)  [envs DB_*, como hoje] → app.state.db_pool
```

## Componentes

### `tenant_app_template/`

- `src/tenant/grpc/` (novo): stubs `saas_agent_pb2.py` e `saas_agent_pb2_grpc.py`
  gerados a partir de `proto/saas_agent.proto`; `scripts/gen_proto.sh` passa a
  gerar também para `tenant_app_template` (com o mesmo fix de import relativo).
  Excluir `src/tenant/grpc/` de black/isort/mypy/coverage (espelho do
  `client_agent_api`).
- `src/tenant/grpc_client.py` (novo): `SaasConfigClient` minimalista (sem cache):
  - `__init__(server, timeout=5.0)`: `grpc.insecure_channel` + stub `AgentBridgeStub`.
  - `get_app_config(app_id) -> saas_agent_pb2.AppConfig`: chama `GetAppConfig`;
    em sucesso loga `"AppConfig received app_id=%s db_host=%s db_port=%s mqtt_topic=%s"`
    (nível `INFO`, sem `db_user`/`db_password`/`db_name`) e retorna o `AppConfig`;
    em `grpc.RpcError` loga `error` e lança `TenantBootstrapError`.
  - `close()`: fecha o canal.
- `src/tenant/config.py`: adiciona `app_id: str = "app-abc123"`,
  `saas_grpc_host: str = "localhost:50051"`, `grpc_timeout_seconds: float = 5.0`.
- `src/tenant/main.py`: no `lifespan`, após criar o pool, cria o `SaasConfigClient`,
  chama `get_app_config(settings.app_id)` via `asyncio.to_thread` (chamada bloqueante)
  e fecha o client; em `TenantBootstrapError` loga `warning` e segue. Adiciona
  `logging.basicConfig(level=INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")`
  no topo do módulo (hoje os `logger.info` do `tenant.main` não aparecem no
  `docker logs` porque o uvicorn não configura o root logger).
- `pyproject.toml`: adiciona `grpcio` e `protobuf` em `dependencies`; `grpcio-tools`,
  `types-grpcio` e `types-protobuf` em `[dependency-groups].dev`.

### Documentação / env

- `tenant_app_template/.env.example`: adiciona `SAAS_GRPC_HOST=localhost:50051`
  (`APP_ID` já existe).
- `tenant_app_template/docker-compose.yml`: repassa `SAAS_GRPC_HOST=${SAAS_GRPC_HOST}`
  ao serviço `tenant_app`.
- `tenant_app_template/README.md`: documenta o fluxo gRPC de startup e as envs
  novas (`APP_ID`, `SAAS_GRPC_HOST`).

## Erros e degradação

- SaaS inacessível / `app_id` inválido ou não encontrado → `grpc_client` loga
  `error`, levanta `TenantBootstrapError`; o `lifespan` captura, loga `warning`
  e o app sobe normalmente (`/health` ok, `/ingest` segue pelas envs `DB_*`).
- O canal gRPC é fechado tanto em sucesso quanto em falha.

## Testes

- `tests/test_config.py`: defaults novos (`app_id`, `saas_grpc_host`,
  `grpc_timeout_seconds`).
- `tests/test_grpc_client.py` (novo):
  - `get_app_config` mapeia a resposta e loga `AppConfig received` (caplog);
  - `RpcError` → `TenantBootstrapError`;
  - o log não contém `db_password`/`db_user`.
- `tests/test_main.py` (novo): `lifespan` chama `get_app_config(settings.app_id)`
  com o `SaasConfigClient` mockado; falha de `get_app_config` não impede o startup.
- Gate: `task lint && task test` em `tenant_app_template`.

## Verificação

1. `task lint && task test` em `tenant_app_template`.
2. E2E: subir o SaaS Backend (gRPC `agent_bridge` na porta 50051) e o `tenant_app`
   com `SAAS_GRPC_HOST` apontando para ele; conferir `AppConfig received` no
   stdout/`docker logs`.

## Decisões e riscos

- **Client sem cache:** a S2 exige a prova de comunicação no startup; cache/uso
  on-demand ficam para a #47/#35 (YAGNI).
- **Log em inglês (token exigido):** o token `AppConfig received` é exigido pelos
  critérios de aceite; mantemos `key=value` no resto (estilo já usado em
  `Falha gRPC GetAppConfig app_id=... code=...`).
- **Default `saas_grpc_host=localhost:50051`** (dev); em container apontar para o
  endereço alcançável do SaaS (documentado), igual ao `client_agent_api`.
- **Risco:** o canal gRPC `insecure_channel` trafega `db_password` em claro no
  `AppConfig`; nesta issue não logamos esses campos e o TLS/mTLS é da Sprint 5
  (já anotado em `proto/README.md`).
