# Issue #58 — Provisionamento Docker via Serviço gRPC

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para implementar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Goal:** Implementar o endpoint `POST /api/v1/tenant/{tenant_id}/applications/{application_id}/provision` no `identity_api`, que valida a aplicação e chama por gRPC o novo serviço `docker_provisioner`; o provisioner cria um container Docker mínimo por aplicação, com porta aleatória `8100–9100`, rede dedicada, envs injetadas e retorno de `container_id`/`port`.

**Architecture:** O `identity_api` permanece como plano de controle REST e não acessa o Docker daemon. O novo `linx_core/services/docker_provisioner` expõe gRPC em `:50052`, autentica chamadas com `authorization: Bearer <SERVICE_TOKEN>`, valida o `app_id`, orquestra o Docker via `docker-py` e devolve apenas dados públicos. Cada aplicação tem no máximo um container, identificado por label `linx.application.id=<app_id>`, em rede `linx-app-<app_id>`. Não há persistência em `application_instances` nesta issue.

**Tech Stack:** Python 3.12, FastAPI 0.141.x, gRPC (`grpcio`/`protobuf`), `docker` 7.x, Poetry, SQLAlchemy (somente no `identity_api` para validar a application), Docker Compose, pytest.

**Spec:** GitHub issue #58 + decisões aprovadas nesta sessão. A issue original usa nomes antigos (`saas_backend`, `tenant_app_template`); este plano aplica o escopo ao layout atual (`linx_core/services` e `client/`).

## Global Constraints

- Trabalhar em branch criada a partir de `origin/develop` atualizado: `feat/58-docker-provisioning-grpc`.
- Não fazer commit, push ou PR sem aprovação explícita após a validação manual do usuário.
- Usar Poetry para adicionar dependências Python.
- Comentar as principais partes do código para entendimento da equipe.
- Não implementar `application_instances` (#59), auto-trigger (#60), retry (#106) nem indicador de status (#54).
- Endpoint HTTP tenant-scoped no `identity_api`: `POST /api/v1/tenant/{tenant_id}/applications/{application_id}/provision`.
- O `identity_api` não monta `/var/run/docker.sock`; somente o `docker_provisioner` acessa o Docker daemon.
- gRPC interno em `docker_provisioner:50052`; não publicar a porta no host.
- Autenticação gRPC: metadado `authorization: Bearer <SERVICE_TOKEN>`, comparação em tempo constante.
- Request gRPC: apenas `app_id`. O provisioner decide imagem, porta, rede e envs.
- Response gRPC: `container_id`, `port`, `network`, `image`, `status`, `created`, `mqtt_topic`. Nunca retornar `DB_PASSWORD`.
- Container idempotente por label Docker; no máximo um container por `application_id`.
- Porta aleatória criptograficamente segura no range `8100–9100`, publicada em `0.0.0.0`.
- Rede Docker dedicada por aplicação: `linx-app-<app_id>`.
- Envs injetadas no container: `APP_ID`, `DB_PASSWORD`, `MQTT_TOPIC`, `SERVICE_TOKEN`.
- `DB_PASSWORD` é aleatório e efêmero (`secrets.token_urlsafe(16)`); fica apenas no env do container.
- `SERVICE_TOKEN` é o mesmo token do plano de controle, usado na autenticação gRPC e injetado no container do tenant.
- A imagem mínima do tenant expõe `/health` público e `/info` protegido por `X-Service-Token`; nunca expõe `DB_PASSWORD`.
- Não alterar `deploy/docker-compose.yml` nesta issue.

## Review Focus

- `identity_api` e `docker_provisioner` podem ficar fora de sincronia no contrato: stubs gerados no `linx_shared` devem ser a única fonte e o CI de proto-drift deve passar.
- Falha do provisioner não pode virar 500 genérico: mapear `UNAVAILABLE` para 503, `DEADLINE_EXCEEDED` para 504, `RESOURCE_EXHAUSTED` para 503 e erros de Docker para 502.
- Chamadas repetidas ao endpoint não podem criar containers duplicados: buscar por label cobrindo containers parados.
- Porta sorteada pode colidir com processo do host ou container existente: consultar portas publicadas no Docker e tentar bind no host.
- O container do tenant não pode expor `DB_PASSWORD`: `/info` retorna apenas indicadores não sensíveis.
- O socket Docker dá poder equivalente a root no host: documentar o risco e exigir `DOCKER_GID` explícito no compose de desenvolvimento.

---

## File Structure

- `proto/linx_docker_provisioner.proto` — contrato gRPC `DockerProvisioner`.
- `scripts/gen_proto.sh` — gera stubs dos dois contratos no `linx_shared`.
- `linx_core/shared/src/linx_shared/grpc/linx_docker_provisioner_pb2*.py` — stubs gerados e versionados.
- `linx_core/services/docker_provisioner/` — serviço gRPC, lógica Docker, config, Dockerfile e testes.
- `linx_core/services/identity_api/src/identity_api/provisioner_client.py` — cliente gRPC e mapeamento de erros.
- `linx_core/services/identity_api/src/identity_api/schemas.py` — schema HTTP de resposta.
- `linx_core/services/identity_api/src/identity_api/routes/application.py` — endpoint de provisionamento.
- `linx_core/services/identity_api/src/identity_api/config.py` — host/timeout do provisioner.
- `linx_core/services/identity_api/src/identity_api/dependencies.py` — dependency do cliente gRPC.
- `client/tenant_app/` — app FastAPI mínimo, Dockerfile e testes da imagem do tenant.
- `linx_core/docker-compose.yml` — serviço `docker_provisioner` com socket Docker.
- `linx_core/.env.example` — token, `DOCKER_GID`, `PROVISION_*`, `PROVISIONER_GRPC_*`.
- `Makefile` — alvo `build-tenant-image`.
- `.github/workflows/backend-ci.yml` — matriz inclui `services/docker_provisioner`.
- `linx_core/pyproject.toml` — task `test` inclui o provisioner.
- `linx_core/scripts/run.sh` — sobe o provisioner junto no modo dev.
- `linx_core/README.md`, `client/README.md`, `proto/README.md`, `docs/comunicacao_entre_servicos.md`, `docs/estrutura_de_pastas/estrutura.md` — documentação.
- `docs/openapi-stub.json` — contrato OpenAPI regenerado.
- `linx_core/services/identity_api/tests/test_openapi.py` — asserção do novo endpoint.

---

### Task 1: Branch, contrato gRPC e stubs

**Files:**
- Create: `proto/linx_docker_provisioner.proto`
- Modify: `scripts/gen_proto.sh`
- Create: `linx_core/shared/src/linx_shared/grpc/linx_docker_provisioner_pb2.py`
- Create: `linx_core/shared/src/linx_shared/grpc/linx_docker_provisioner_pb2_grpc.py`
- Modify: `proto/README.md`

**Interfaces:**
- Produces: `linx_shared.grpc.linx_docker_provisioner_pb2` e `linx_docker_provisioner_pb2_grpc`.
- Service: `DockerProvisioner.ProvisionApplication(ProvisionApplicationRequest) returns (ProvisionApplicationResponse)`.

- [ ] **Step 1: Atualizar `develop` e criar a branch**

```bash
git fetch origin develop
git checkout develop
git pull --ff-only origin develop
git checkout -b feat/58-docker-provisioning-grpc
```

Não remover nem adicionar o arquivo não rastreado `client/frontend/src/components/ProvisioningStatus.tsx`; ele pertence a outra issue.

- [ ] **Step 2: Criar `proto/linx_docker_provisioner.proto`**

```proto
syntax = "proto3";

package linx;

// DockerProvisioner é o contrato interno entre o identity_api e o serviço
// que cria e mantém containers Docker por aplicação.
service DockerProvisioner {
  rpc ProvisionApplication(ProvisionApplicationRequest)
      returns (ProvisionApplicationResponse);
}

message ProvisionApplicationRequest {
  string app_id = 1;
}

message ProvisionApplicationResponse {
  string container_id = 1;
  uint32 port = 2;
  string network = 3;
  string image = 4;
  string status = 5;
  bool created = 6;
  string mqtt_topic = 7;
}
```

- [ ] **Step 3: Atualizar `scripts/gen_proto.sh`**

Gerar os dois protos no mesmo diretório e corrigir o import absoluto para relativo em ambos os `_pb2_grpc.py`. Para o novo contrato, a correção deve transformar:

```python
import linx_docker_provisioner_pb2 as linx__docker__provisioner__pb2
```

em:

```python
from . import linx_docker_provisioner_pb2 as linx__docker__provisioner__pb2
```

Manter o comportamento atual para `linx_agent.proto`.

- [ ] **Step 4: Gerar e verificar os stubs**

```bash
bash scripts/gen_proto.sh
git status --short linx_core/shared/src/linx_shared/grpc
```

Expected: os quatro arquivos `linx_agent_pb2*.py` e `linx_docker_provisioner_pb2*.py` existem; nenhum import absoluto quebrado.

- [ ] **Step 5: Documentar o contrato em `proto/README.md`**

Adicionar seção do `DockerProvisioner` com:
- direção `identity_api → docker_provisioner`;
- request/response;
- porta `50052`;
- auth `authorization: Bearer <SERVICE_TOKEN>`;
- aviso de que `DB_PASSWORD` não trafega no gRPC.

---

### Task 2: Implementar o núcleo Docker do provisioner (TDD)

**Files:**
- Create: `linx_core/services/docker_provisioner/pyproject.toml`
- Create: `linx_core/services/docker_provisioner/poetry.lock`
- Create: `linx_core/services/docker_provisioner/src/docker_provisioner/__init__.py`
- Create: `linx_core/services/docker_provisioner/src/docker_provisioner/config.py`
- Create: `linx_core/services/docker_provisioner/src/docker_provisioner/docker_service.py`
- Create: `linx_core/services/docker_provisioner/tests/test_docker_service.py`
- Create: `linx_core/services/docker_provisioner/tests/fakes.py`

**Interfaces:**
- Produces:
  - `class ProvisioningError(RuntimeError)` com `message: str` e `status: grpc.StatusCode`.
  - `@dataclass(frozen=True) class ProvisionResult` com `container_id: str`, `port: int`, `network: str`, `image: str`, `status: str`, `created: bool`, `mqtt_topic: str`.
  - `def allocate_port(client: DockerClient, port_min: int, port_max: int, bind_host: str, *, rng: random.Random | None = None) -> int`.
  - `def ensure_network(client: DockerClient, app_id: str, prefix: str) -> Network`.
  - `def provision_application(client: DockerClient, app_id: str, *, image: str, port_min: int, port_max: int, bind_host: str, network_prefix: str, container_port: int, service_token: str) -> ProvisionResult`.

- [ ] **Step 1: Criar o projeto Poetry do provisioner**

`pyproject.toml`:
- nome `docker-provisioner`;
- pacote `docker_provisioner` em `src`;
- `linx-shared = { path = "../../shared", develop = true }`;
- deps: `grpcio`, `protobuf`, `docker` `^7.1`, `pydantic-settings`;
- dev: `pytest`, `pytest-cov`, `black`, `flake8`, `mypy`, `isort`, `taskipy`, `grpcio-tools`;
- overrides mypy para `docker` e `docker.*`;
- tasks `lint`, `lint-check`, `test`, `run`.

```bash
poetry -C linx_core/services/docker_provisioner lock
poetry -C linx_core/services/docker_provisioner install
```

- [ ] **Step 2: Implementar `config.py`**

Settings:
```python
grpc_host: str = "0.0.0.0"
grpc_port: int = 50052
provision_image: str = "linx-tenant-app:latest"
provision_port_min: int = 8100
provision_port_max: int = 9100
provision_bind_host: str = "0.0.0.0"
provision_network_prefix: str = "linx-app"
provision_container_port: int = 8000
```

Herdar `linx_shared.core.config.Settings` para obter `service_token`.
Validar no startup:
- `SERVICE_TOKEN` não vazio, mínimo 32 caracteres, sem placeholders conhecidos;
- range de portas em `1..65535` e `min <= max`;
- imagem, bind host e prefixo de rede não vazios.

- [ ] **Step 3: Escrever testes que falham para alocação de porta**

Em `tests/test_docker_service.py`, cobrir:
- porta retornada dentro de `[8100, 9100]`;
- portas já publicadas por containers são ignoradas;
- portas ocupadas no host (bind falha) são ignoradas;
- range esgotado levanta `ProvisioningError` com `grpc.StatusCode.RESOURCE_EXHAUSTED`;
- `rng` semeado permite teste determinístico, mas a produção usa `secrets.SystemRandom`.

Usar fake de Docker que exponha `containers.list(all=True)` com `attrs["NetworkSettings"]["Ports"]`, e monkeypatch de `socket.socket` para simular bind ocupado/livre.

- [ ] **Step 4: Rodar e verificar falha**

```bash
poetry -C linx_core/services/docker_provisioner run pytest tests/test_docker_service.py -q
```

Expected: FAIL porque `docker_service.py` ainda não implementa o comportamento.

- [ ] **Step 5: Implementar alocação de porta em `docker_service.py`**

Regras:
- coletar portas de host publicadas por todos os containers (`all=True`), inclusive parados;
- sortear candidatos com `secrets.SystemRandom()` em produção ou `rng` injetado em teste;
- testar bind em `(bind_host, porta)` com `socket.AF_INET`/`SOCK_STREAM`; fechar o socket em seguida;
- se não houver porta livre, levantar `ProvisioningError(..., status=grpc.StatusCode.RESOURCE_EXHAUSTED)`;
- não usar `random.random`/`random.randint` diretamente.

- [ ] **Step 6: Escrever testes que falham para rede, idempotência e container**

Cobrir:
- criação de rede `linx-app-<app_id>` quando não existe;
- reutilização da rede quando já existe;
- container criado com:
  - `name=linx-app-<app_id>`;
  - labels `linx.managed-by=linx-core` e `linx.application.id=<app_id>`;
  - `ports={"8000/tcp": ("0.0.0.0", porta)}`;
  - env `APP_ID`, `DB_PASSWORD`, `MQTT_TOPIC=application/<app_id>/device/+/event/up`, `SERVICE_TOKEN`;
  - `detach=True`;
  - `restart_policy={"Name": "unless-stopped"}`;
  - `security_opt=["no-new-privileges:true"]`;
- retorno `created=True` na primeira chamada;
- segunda chamada com container existente retorna o mesmo `container_id`/porta e `created=False`;
- container existente parado é iniciado antes do retorno;
- mais de um container com o mesmo label levanta `ProvisioningError(status=grpc.StatusCode.ABORTED)`;
- `docker.errors.ImageNotFound` levanta `ProvisioningError(status=grpc.StatusCode.FAILED_PRECONDITION)`;
- `docker.errors.DockerException` ao listar containers levanta `ProvisioningError(status=grpc.StatusCode.UNAVAILABLE)`;
- `docker.errors.APIError` ao criar container levanta `ProvisioningError(status=grpc.StatusCode.INTERNAL)`;
- porta já alocada no `containers.run` tenta nova porta, no máximo 5 tentativas.

- [ ] **Step 7: Rodar e verificar falha**

```bash
poetry -C linx_core/services/docker_provisioner run pytest tests/test_docker_service.py -q
```

Expected: FAIL nos comportamentos ainda não implementados.

- [ ] **Step 8: Implementar rede, idempotência e criação do container**

Regras:
- `ensure_network`: buscar por nome; se `docker.errors.NotFound`, criar com driver `bridge` e labels `linx.managed-by`/`linx.application.id`.
- Buscar container por label com `client.containers.list(all=True, filters={"label": f"linx.application.id={app_id}"})`.
- Se existir:
  - `container.reload()`;
  - se `status != "running"`, chamar `container.start()`;
  - ler a porta publicada em `attrs["NetworkSettings"]["Ports"][f"{container_port}/tcp"][0]["HostPort"]`;
  - se não houver porta publicada, levantar `ProvisioningError(status=grpc.StatusCode.INTERNAL)`.
- Se não existir:
  - alocar porta;
  - garantir rede;
  - executar `client.containers.run(image, ...)` com os parâmetros testados;
  - em erro de porta já alocada (`APIError` contendo `port is already allocated` ou `address already in use`), tentar novamente com nova porta, no máximo 5 tentativas;
  - retornar `ProvisionResult(created=True)`.
- `DB_PASSWORD` é gerado com `secrets.token_urlsafe(16)` no momento da criação e nunca entra no `ProvisionResult`.
- Não persistir nada no Postgres.

- [ ] **Step 9: Rodar e verificar sucesso**

```bash
poetry -C linx_core/services/docker_provisioner run pytest tests/test_docker_service.py -q
```

Expected: PASS.

---

### Task 3: Expor o servidor gRPC do provisioner

**Files:**
- Create: `linx_core/services/docker_provisioner/src/docker_provisioner/server.py`
- Create: `linx_core/services/docker_provisioner/src/docker_provisioner/__main__.py` (opcional; o Dockerfile pode usar `-m docker_provisioner.server`)
- Create: `linx_core/services/docker_provisioner/Dockerfile`
- Create: `linx_core/services/docker_provisioner/tests/test_server.py`
- Modify: `linx_core/services/docker_provisioner/tests/fakes.py`

**Interfaces:**
- Consumes: `provision_application(...)` e `ProvisioningError` da Task 2.
- Produces:
  - `class DockerProvisionerServicer(linx_docker_provisioner_pb2_grpc.DockerProvisionerServicer)`.
  - `def authorize(context) -> None`.
  - `def create_server(servicer=None) -> grpc.Server`.
  - `def serve() -> None`.

- [ ] **Step 1: Escrever testes que falham para auth e gRPC**

Em `tests/test_server.py`, cobrir:
- `authorize` aceita `authorization: Bearer <SERVICE_TOKEN>`;
- `authorize` aborta `UNAUTHENTICATED` sem metadado, com token errado ou token não configurado;
- `ensure_service_token` rejeita token vazio, placeholder e menor que 32 caracteres;
- `ProvisionApplication` valida `app_id` UUID e aborta `INVALID_ARGUMENT` se inválido;
- `ProvisionApplication` chama `provision_application` e devolve todos os campos;
- `ProvisioningError` é convertido para o `grpc.StatusCode` correspondente;
- servidor de teste em porta efêmera (`127.0.0.1:0`) responde via stub real;
- `create_server` falha se o bind retornar 0.

- [ ] **Step 2: Rodar e verificar falha**

```bash
poetry -C linx_core/services/docker_provisioner run pytest tests/test_server.py -q
```

Expected: FAIL porque `server.py` ainda não existe.

- [ ] **Step 3: Implementar `server.py`**

Seguir o padrão do `agent_bridge`:
- `AUTH_METADATA_KEY = "authorization"`;
- `BEARER_PREFIX = "Bearer "`;
- `_extract_bearer_token`;
- `authorize(context)` com `secrets.compare_digest` e falha fechada;
- `ensure_service_token()` no startup;
- `DockerProvisionerServicer.__init__(client_factory=docker.from_env)`;
- `ProvisionApplication` valida UUID, chama o núcleo e retorna o protobuf;
- `create_server` usa `ThreadPoolExecutor(max_workers=10)`, bind inseguro em `GRPC_HOST:GRPC_PORT` e loga aviso de modo inseguro;
- `serve()` valida token, cria servidor, inicia e aguarda terminação.

Não implementar TLS nesta issue; documentar que a proteção atual é rede interna + token.

- [ ] **Step 4: Criar o Dockerfile**

Copiar o padrão do `agent_bridge/Dockerfile`:
- builder com `python:3.12.10-slim` e Poetry 2.4.1;
- `COPY shared ./shared`;
- `COPY services/docker_provisioner ./services/docker_provisioner`;
- instala sem dev;
- runtime com usuário `appuser`;
- `PYTHONPATH=/app/services/docker_provisioner/src:/app/shared/src`;
- `EXPOSE 50052`;
- `CMD ["python", "-m", "docker_provisioner.server"]`.

- [ ] **Step 5: Rodar e verificar sucesso**

```bash
poetry -C linx_core/services/docker_provisioner run pytest tests/test_server.py -q
```

Expected: PASS.

---

### Task 4: Cliente gRPC e endpoint no `identity_api`

**Files:**
- Create: `linx_core/services/identity_api/src/identity_api/provisioner_client.py`
- Create: `linx_core/services/identity_api/src/identity_api/schemas.py`
- Modify: `linx_core/services/identity_api/src/identity_api/config.py`
- Modify: `linx_core/services/identity_api/src/identity_api/dependencies.py`
- Modify: `linx_core/services/identity_api/src/identity_api/main.py`
- Modify: `linx_core/services/identity_api/src/identity_api/routes/application.py`
- Create: `linx_core/services/identity_api/tests/test_provisioner_client.py`
- Create: `linx_core/services/identity_api/tests/test_application_provision.py`
- Modify: `linx_core/services/identity_api/tests/fakes.py`
- Modify: `linx_core/services/identity_api/tests/test_openapi.py`

**Interfaces:**
- Consumes: stubs da Task 1 e `ProvisioningError`/servidor da Task 3.
- Produces:
  - `class ProvisionerClientError(RuntimeError)` com `message: str` e `status_code: int`.
  - `class DockerProvisionerClient` com `provision(app_id: str) -> ProvisionedApplication` e `close() -> None`.
  - `@dataclass(frozen=True) class ProvisionedApplication` com os campos públicos do response.
  - `def get_provisioner_client() -> DockerProvisionerClient`.
  - `def close_provisioner_client() -> None`.
  - `class ProvisionResponse(BaseModel)`.
  - `POST /api/v1/tenant/{tenant_id}/applications/{application_id}/provision`.

- [ ] **Step 1: Adicionar `grpcio` explícito ao `identity_api`**

```bash
poetry -C linx_core/services/identity_api add "grpcio@^1.84"
```

- [ ] **Step 2: Adicionar settings do provisioner em `config.py`**

```python
provisioner_grpc_host: str = "localhost:50052"
provisioner_grpc_timeout_seconds: float = 10.0
```

Validar host não vazio e timeout positivo.

- [ ] **Step 3: Escrever testes que falham para o cliente gRPC**

Em `tests/test_provisioner_client.py`, usar um servidor gRPC real em porta efêmera com um servicer fake ou mockar o stub. Cobrir:
- request envia `app_id` e metadado `authorization: Bearer <SERVICE_TOKEN>`;
- resposta converte todos os campos para `ProvisionedApplication`;
- `grpc.StatusCode.UNAVAILABLE` → `ProvisionerClientError(status_code=503)`;
- `grpc.StatusCode.DEADLINE_EXCEEDED` → `504`;
- `grpc.StatusCode.RESOURCE_EXHAUSTED` → `503`;
- `grpc.StatusCode.UNAUTHENTICATED`/`PERMISSION_DENIED`/`INVALID_ARGUMENT`/`FAILED_PRECONDITION`/`INTERNAL` → `502`;
- `grpc.StatusCode.ABORTED` → `409`;
- `close()` fecha o canal.

- [ ] **Step 4: Rodar e verificar falha**

```bash
poetry -C linx_core/services/identity_api run pytest tests/test_provisioner_client.py -q
```

Expected: FAIL porque `provisioner_client.py` ainda não existe.

- [ ] **Step 5: Implementar `provisioner_client.py`**

Regras:
- criar `grpc.insecure_channel(settings.provisioner_grpc_host)` no construtor;
- criar stub `linx_docker_provisioner_pb2_grpc.DockerProvisionerStub`;
- enviar `metadata=(("authorization", f"Bearer {settings.service_token}"),)`;
- usar `timeout=settings.provisioner_grpc_timeout_seconds`;
- mapear `grpc.RpcError` conforme a tabela testada;
- `close()` fecha o canal;
- não expor o token em logs.

- [ ] **Step 6: Implementar dependency e lifespan**

Em `dependencies.py`:
- `@lru_cache _build_provisioner_client()`;
- `get_provisioner_client()`;
- `close_provisioner_client()` fecha e limpa o cache.

Em `main.py`, chamar `close_provisioner_client()` no final do lifespan, junto de `close_chirpstack_client()`.

- [ ] **Step 7: Escrever testes HTTP que falham**

Em `tests/test_application_provision.py`, usar `TestClient(app, headers=AUTH)` e override de `get_provisioner_client` com fake. Cobrir:
- `201` na primeira chamada, com `container_id`, `port`, `network`, `image`, `status`, `created=True`, `mqtt_topic`;
- `200` na segunda chamada idempotente, com os mesmos dados e `created=False`;
- `404` para tenant inexistente;
- `404` para application inexistente;
- `404` para application de outro tenant;
- `401` sem `X-Service-Token`;
- `503` quando o cliente levanta `ProvisionerClientError(status_code=503)`;
- `504` quando o cliente levanta `ProvisionerClientError(status_code=504)`;
- `502` quando o cliente levanta `ProvisionerClientError(status_code=502)`;
- `409` quando o cliente levanta `ProvisionerClientError(status_code=409)`.

- [ ] **Step 8: Rodar e verificar falha**

```bash
poetry -C linx_core/services/identity_api run pytest tests/test_application_provision.py -q
```

Expected: FAIL porque a rota ainda não existe.

- [ ] **Step 9: Implementar `schemas.py`**

```python
class ProvisionResponse(BaseModel):
    container_id: str
    port: int
    network: str
    image: str
    status: str
    created: bool
    mqtt_topic: str
```

- [ ] **Step 10: Implementar a rota em `routes/application.py`**

Adicionar, seguindo o padrão dos outros endpoints:
- `response_model=ProvisionResponse`;
- `status_code=201` por padrão; trocar para `200` quando `created=False`;
- validar `Tenant` e `Application` (incluindo `application.tenant_id == tenant_id`);
- chamar `get_provisioner_client().provision(str(application_id))`;
- capturar `ProvisionerClientError` e responder `HTTPException(status_code=exc.status_code, detail=exc.message)`;
- documentar `responses={404, 409, 502, 503, 504}` no decorator;
- comentar o fluxo principal (validação, chamada gRPC, idempotência, retorno).

- [ ] **Step 11: Rodar e verificar sucesso**

```bash
poetry -C linx_core/services/identity_api run pytest tests/test_provisioner_client.py tests/test_application_provision.py -q
```

Expected: PASS.

- [ ] **Step 12: Atualizar o teste de OpenAPI**

Em `tests/test_openapi.py`, adicionar asserção:

```python
assert "post" in paths[
    "/api/v1/tenant/{tenant_id}/applications/{application_id}/provision"
]
```

- [ ] **Step 13: Rodar os testes de aplicação e OpenAPI**

```bash
poetry -C linx_core/services/identity_api run pytest tests/test_applications.py tests/test_application_provision.py tests/test_openapi.py -q
```

Expected: PASS ou falha apenas do stub até a Task 7 regenerar `docs/openapi-stub.json`.

---

### Task 5: Criar a imagem mínima do tenant

**Files:**
- Create: `client/tenant_app/pyproject.toml`
- Create: `client/tenant_app/poetry.lock`
- Create: `client/tenant_app/Dockerfile`
- Create: `client/tenant_app/src/tenant_app/__init__.py`
- Create: `client/tenant_app/src/tenant_app/app.py`
- Create: `client/tenant_app/tests/test_app.py`
- Create: `client/tenant_app/README.md`
- Modify: `client/README.md`

**Interfaces:**
- Produces:
  - imagem `linx-tenant-app:latest`;
  - `GET /health` público;
  - `GET /info` protegido por `X-Service-Token`.

- [ ] **Step 1: Criar o app mínimo e os testes**

`app.py` deve:
- ler `APP_ID`, `MQTT_TOPIC`, `SERVICE_TOKEN` e `DB_PASSWORD` do ambiente em tempo de requisição;
- `GET /health` retornar `{"status": "ok", "app_id": "<APP_ID>"}` sem autenticação;
- `GET /info`:
  - exigir header `X-Service-Token`;
  - retornar `503` se `SERVICE_TOKEN` não estiver configurado;
  - retornar `401` se o token não bater, usando `secrets.compare_digest`;
  - retornar `app_id`, `mqtt_topic` e `db_password_configured` (booleano), nunca a senha;
- `create_app()` para permitir testes com `TestClient`.

Em `tests/test_app.py`, cobrir:
- `/health` público;
- `/info` sem token → `401`;
- `/info` com token errado → `401`;
- `/info` com token correto → `200` e `db_password_configured=True`;
- resposta não contém o valor de `DB_PASSWORD`.

- [ ] **Step 2: Criar `pyproject.toml` e gerar o lock**

Dependências: `fastapi`, `uvicorn[standard]`.
Dev: `pytest`, `httpx`, `black`, `isort`, `flake8`, `mypy`, `taskipy`.

Definir tasks:

```toml
[tool.taskipy.tasks]
lint = "black . && isort . && mypy src tests && flake8 src tests"
test = "pytest -q"
```

```bash
poetry -C client/tenant_app lock
poetry -C client/tenant_app install
```

- [ ] **Step 3: Rodar os testes do app mínimo**

```bash
poetry -C client/tenant_app run pytest -q
```

Expected: PASS.

- [ ] **Step 4: Criar o Dockerfile multi-stage**

Requisitos:
- builder com `python:3.12-slim` e Poetry;
- runtime com `python:3.12-slim`;
- usuário não-root `appuser`;
- `EXPOSE 8000`;
- `HEALTHCHECK` chamando `http://localhost:8000/health`;
- `CMD ["uvicorn", "tenant_app.app:app", "--host", "0.0.0.0", "--port", "8000"]`.

- [ ] **Step 5: Buildar e validar a imagem isoladamente**

```bash
docker build -t linx-tenant-app:latest client/tenant_app
docker run --rm -d --name linx-tenant-app-check \
  -e APP_ID=check-app \
  -e MQTT_TOPIC=application/check-app/device/+/event/up \
  -e DB_PASSWORD=check-db-password \
  -e SERVICE_TOKEN=check-service-token-0123456789abcdef \
  -p 127.0.0.1:18100:8000 \
  linx-tenant-app:latest
curl -s http://127.0.0.1:18100/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18100/info
curl -s -H 'X-Service-Token: check-service-token-0123456789abcdef' \
  http://127.0.0.1:18100/info
docker rm -f linx-tenant-app-check
```

Expected: `/health` 200; `/info` sem token 401; `/info` com token 200 e sem senha no corpo.

- [ ] **Step 6: Documentar a imagem**

Atualizar `client/README.md` com:
- finalidade da imagem mínima;
- comando de build;
- envs esperadas;
- endpoints `/health` e `/info`;
- aviso de que não substitui o `telemetry_consumer` completo.

---

### Task 6: Integrar no compose, tarefas e CI

**Files:**
- Modify: `linx_core/docker-compose.yml`
- Modify: `linx_core/.env.example`
- Modify: `Makefile`
- Modify: `linx_core/pyproject.toml`
- Modify: `linx_core/scripts/run.sh`
- Modify: `.github/workflows/backend-ci.yml`

**Interfaces:**
- Consumes: imagem `linx-tenant-app:latest` da Task 5; serviço da Task 3; cliente da Task 4.
- Produces: `docker_provisioner` em `linx_core/docker-compose.yml`, acessível em `docker_provisioner:50052`.

- [ ] **Step 1: Adicionar `docker_provisioner` ao compose**

```yaml
  docker_provisioner:
    build:
      context: .
      dockerfile: services/docker_provisioner/Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      - GRPC_HOST=0.0.0.0
      - GRPC_PORT=50052
      - SERVICE_TOKEN=${SERVICE_TOKEN:?SERVICE_TOKEN must be set}
      - PROVISION_IMAGE=${PROVISION_IMAGE:-linx-tenant-app:latest}
      - PROVISION_PORT_MIN=${PROVISION_PORT_MIN:-8100}
      - PROVISION_PORT_MAX=${PROVISION_PORT_MAX:-9100}
      - PROVISION_BIND_HOST=${PROVISION_BIND_HOST:-0.0.0.0}
      - PROVISION_NETWORK_PREFIX=${PROVISION_NETWORK_PREFIX:-linx-app}
      - PROVISION_CONTAINER_PORT=${PROVISION_CONTAINER_PORT:-8000}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    group_add:
      - "${DOCKER_GID:?DOCKER_GID must be set}"
    expose:
      - "50052"
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import socket; socket.create_connection(('127.0.0.1', 50052), 2)"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

Comentário de segurança: o socket dá poder equivalente a root no host; usar apenas em ambiente controlado.

- [ ] **Step 2: Configurar o `identity_api` para o provisioner**

No serviço `identity_api` do mesmo compose, adicionar:

```yaml
      - PROVISIONER_GRPC_HOST=${PROVISIONER_GRPC_HOST:-docker_provisioner:50052}
      - PROVISIONER_GRPC_TIMEOUT_SECONDS=${PROVISIONER_GRPC_TIMEOUT_SECONDS:-10}
```

Não montar o socket Docker no `identity_api`.

- [ ] **Step 3: Atualizar `linx_core/.env.example`**

Adicionar, com comentários:

```dotenv
# Token de serviço do plano de controle e da chamada gRPC (mínimo 32 chars).
# Gere com: openssl rand -hex 32
SERVICE_TOKEN=replace-with-a-random-secret-at-least-32-chars

# GID do grupo dono de /var/run/docker.sock no host.
# Descubra com: stat -c '%g' /var/run/docker.sock
DOCKER_GID=990

# Serviço de provisionamento Docker (issue #58).
PROVISIONER_GRPC_HOST=docker_provisioner:50052
PROVISIONER_GRPC_TIMEOUT_SECONDS=10
PROVISION_IMAGE=linx-tenant-app:latest
PROVISION_PORT_MIN=8100
PROVISION_PORT_MAX=9100
PROVISION_BIND_HOST=0.0.0.0
PROVISION_NETWORK_PREFIX=linx-app
PROVISION_CONTAINER_PORT=8000
```

- [ ] **Step 4: Adicionar alvo de build no `Makefile`**

```make
.PHONY: build-tenant-image
build-tenant-image:
	docker build -t linx-tenant-app:latest client/tenant_app
```

- [ ] **Step 5: Atualizar task runner e `run.sh`**

Em `linx_core/pyproject.toml`:
- atualizar a descrição para citar `docker_provisioner`;
- incluir `poetry -C services/docker_provisioner run pytest` no task `test`.

Em `linx_core/scripts/run.sh`:
- subir `poetry -C services/docker_provisioner run python -m docker_provisioner.server &`;
- adicionar o PID ao array de cleanup;
- exigir `SERVICE_TOKEN` no ambiente; o provisioner usa o socket Docker local padrão.

- [ ] **Step 6: Atualizar o CI**

Em `.github/workflows/backend-ci.yml`:
- adicionar `services/docker_provisioner` à matriz de `lint` e `test`;
- instalar `poetry -C services/docker_provisioner install` no job de testes;
- manter o job `proto-drift` regenerando os dois stubs.

- [ ] **Step 7: Verificar configuração e testes**

```bash
DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
SERVICE_TOKEN="$SERVICE_TOKEN" \
docker compose -f linx_core/docker-compose.yml config >/dev/null
poetry -C linx_core/services/docker_provisioner run pytest -q
poetry -C linx_core/services/identity_api run pytest tests/test_application_provision.py -q
```

Expected: `config` sem erro; testes passam.

---

### Task 7: Atualizar OpenAPI e documentação

**Files:**
- Modify: `docs/openapi-stub.json`
- Modify: `linx_core/README.md`
- Modify: `client/README.md`
- Modify: `proto/README.md`
- Modify: `docs/comunicacao_entre_servicos.md`
- Modify: `docs/estrutura_de_pastas/estrutura.md`

- [ ] **Step 1: Regenerar o stub OpenAPI**

```bash
poetry -C linx_core/services/identity_api run python - <<'PY'
import json
from pathlib import Path

from identity_api.main import app

# O Poetry com -C muda o cwd para services/identity_api.
repo_root = Path.cwd().parents[2]
path = repo_root / "docs" / "openapi-stub.json"
path.write_text(
    json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY
```

Executar a partir da raiz do repositório.

- [ ] **Step 2: Conferir o diff do stub**

```bash
git diff -- docs/openapi-stub.json
```

Expected: apenas a nova rota, o novo schema e ajustes decorrentes aparecem.

- [ ] **Step 3: Atualizar `linx_core/README.md`**

Adicionar:
- `docker_provisioner` na estrutura e na lista de serviços;
- rota de provisionamento na tabela da API;
- seção "Provisionamento Docker" com request/response, status codes `201`, `200`, `401`, `404`, `409`, `502`, `503`, `504`;
- explicação da idempotência por label, range de porta, bind `0.0.0.0`, rede por app;
- aviso de que `DB_PASSWORD` não é retornado;
- aviso do socket Docker e como obter `DOCKER_GID`;
- comandos de build da imagem e validação manual.

- [ ] **Step 4: Atualizar `proto/README.md`**

Documentar o contrato `DockerProvisioner`, a porta `50052`, a auth Bearer e a geração dos stubs.

- [ ] **Step 5: Atualizar documentação de comunicação e estrutura**

Em `docs/comunicacao_entre_servicos.md`, adicionar a chamada interna:
`identity_api --gRPC--> docker_provisioner --Docker API--> daemon`.

Em `docs/estrutura_de_pastas/estrutura.md`, incluir `services/docker_provisioner`.

- [ ] **Step 6: Rodar novamente os testes de OpenAPI**

```bash
poetry -C linx_core/services/identity_api run pytest tests/test_openapi.py -q
```

Expected: PASS.

---

### Task 8: Verificação completa e validação manual

**Files:** nenhum arquivo novo; apenas execução e correções.

- [ ] **Step 1: Rodar lint e testes do `identity_api`**

```bash
poetry -C linx_core/services/identity_api run task lint
poetry -C linx_core/services/identity_api run pytest --cov=src --cov-report=term-missing --cov-fail-under=70
```

Expected: lint e testes passam; cobertura ≥ 70%.

Se não houver Postgres local, subir um banco descartável:

```bash
docker run --rm -d --name linx-test-postgres \
  -e POSTGRES_USER=linx \
  -e POSTGRES_PASSWORD=ci-db-pass \
  -e POSTGRES_DB=linx \
  -p 5432:5432 \
  postgres:15-alpine
```

Depois aplicar migrações:

```bash
poetry -C linx_core/services/identity_api run alembic -c ../../alembic.ini upgrade head
```

Ao final, `docker rm -f linx-test-postgres`.

- [ ] **Step 2: Rodar lint e testes do provisioner**

```bash
poetry -C linx_core/services/docker_provisioner run task lint
poetry -C linx_core/services/docker_provisioner run pytest --cov=src --cov-report=term-missing --cov-fail-under=70
```

Expected: PASS.

- [ ] **Step 3: Rodar lint e testes do app mínimo**

```bash
poetry -C client/tenant_app run task lint
poetry -C client/tenant_app run pytest -q
```

Expected: PASS.

- [ ] **Step 4: Configurar o `.env` local e subir o core**

Adicionar ao `linx_core/.env` local (ignorado pelo git, sem commit):

```dotenv
DOCKER_GID=<saida-de-stat -c '%g' /var/run/docker.sock>
PROVISION_IMAGE=linx-tenant-app:latest
```

Confirmar que `SERVICE_TOKEN` local tem pelo menos 32 caracteres e não é placeholder.

```bash
make build-tenant-image
docker compose -f linx_core/docker-compose.yml up -d --build
```

Expected: `db`, `identity_api` e `docker_provisioner` saudáveis.

- [ ] **Step 5: Validar o fluxo ponta a ponta**

Na raiz do repositório:

```bash
TOKEN="$(grep '^SERVICE_TOKEN=' linx_core/.env | cut -d= -f2-)"
TENANT_ID="$(curl -fsS -X POST http://localhost:8000/api/v1/tenant/ \
  -H "X-Service-Token: $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Tenant Provision Test"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
APP_ID="$(curl -fsS -X POST "http://localhost:8000/api/v1/tenant/$TENANT_ID/applications" \
  -H "X-Service-Token: $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"App Provision Test"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
curl -fsS -X POST "http://localhost:8000/api/v1/tenant/$TENANT_ID/applications/$APP_ID/provision" \
  -H "X-Service-Token: $TOKEN"
docker ps --filter "label=linx.application.id=$APP_ID"
```

Expected:
- resposta JSON com `container_id`, `port`, `network`, `image`, `status="RUNNING"`, `created=true`, `mqtt_topic`;
- `docker ps` mostra `linx-app-$APP_ID` com porta entre `8100` e `9100`;
- segunda chamada retorna `created=false` e a mesma porta;
- logs do `docker_provisioner` não mostram `SERVICE_TOKEN` nem `DB_PASSWORD`.

- [ ] **Step 6: Validar o container provisionado**

```bash
PORT="$(docker inspect -f '{{ (index (index .NetworkSettings.Ports "8000/tcp") 0).HostPort }}' "linx-app-$APP_ID")"
curl -fsS "http://localhost:$PORT/health"
curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:$PORT/info"
curl -fsS -H "X-Service-Token: $TOKEN" "http://localhost:$PORT/info"
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "linx-app-$APP_ID" \
  | grep -E '^(APP_ID|MQTT_TOPIC|SERVICE_TOKEN)='
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "linx-app-$APP_ID" \
  | grep -q '^DB_PASSWORD='
```

Expected:
- `/health` 200;
- `/info` sem token 401;
- `/info` com token 200 e sem `DB_PASSWORD` no corpo;
- envs obrigatórias presentes no container.

- [ ] **Step 7: Validar erros principais**

- Provisionar application inexistente → `404`.
- Provisionar application de outro tenant → `404`.
- Chamar sem `X-Service-Token` → `401`.
- Parar o `docker_provisioner` → `503` no endpoint.
- Usar imagem inexistente (`PROVISION_IMAGE=missing:latest`) → `502`.
- Ocupar todo o range ou simular esgotamento → `503` (preferir teste unitário; não exaurir o range real).

- [ ] **Step 8: Limpar o ambiente de validação**

```bash
docker rm -f "linx-app-$APP_ID"
docker network rm "linx-app-$APP_ID"
docker compose -f linx_core/docker-compose.yml down
```

Não apagar volumes se houver dados que você queira preservar.

- [ ] **Step 9: Apresentar resultado ao usuário**

Relatar:
- arquivos criados/alterados;
- comandos de teste executados e resultados;
- resposta do curl de provisionamento;
- saída de `docker ps`;
- resultados de `/health` e `/info`;
- riscos conhecidos (socket Docker, bind `0.0.0.0`, `DB_PASSWORD` efêmero, gRPC sem TLS nesta issue).

**Parar aqui e aguardar a validação manual do usuário.**

---

### Task 9: Commits, push e PR (somente após aprovação explícita)

**Files:** todos os arquivos alterados/validados.

- [ ] **Step 1: Confirmar aprovação do usuário**

Não executar esta tarefa sem uma mensagem explícita de aprovação após os testes manuais.

- [ ] **Step 2: Revisar o diff e o status**

```bash
git status --short
git diff --stat
git diff
```

Confirmar que `client/frontend/src/components/ProvisioningStatus.tsx` não foi incluído (arquivo de outra issue).

- [ ] **Step 3: Criar commits no padrão Conventional Commits**

Sugestão de commits atômicos:
- `feat(proto): adiciona contrato gRPC do docker_provisioner`
- `feat(docker_provisioner): implementa provisionamento Docker por aplicação`
- `feat(identity_api): aciona provisionamento via gRPC`
- `feat(client): adiciona imagem mínima do tenant`
- `build(linx_core): integra docker_provisioner ao compose e CI`
- `docs: documenta provisionamento Docker e atualiza OpenAPI`

Ajustar conforme o diff final.

- [ ] **Step 4: Push da branch**

```bash
git push -u origin feat/58-docker-provisioning-grpc
```

- [ ] **Step 5: Abrir PR para `develop`**

Usar `gh pr create` com:
- título `feat(backend): provisionamento Docker por aplicação (#58)`;
- corpo com contexto, decisões, mudanças, testes executados, riscos e checklist da issue;
- base `develop`.

- [ ] **Step 6: Aguardar code review**

Corrigir os achados, atualizar a PR e repetir os testes afetados até a aprovação.

---

## Self-Review

- Critérios de aceite da issue #58 cobertos: `containers.run`, porta `8100–9100`, envs `APP_ID`/`DB_PASSWORD`/`MQTT_TOPIC`, retorno `container_id`/`port`.
- Arquitetura solicitada coberta: serviço separado `docker_provisioner`, gRPC `:50052`, `identity_api` como cliente, sem socket Docker no control plane.
- Decisões do usuário cobertas: request só com `app_id`, resposta pública sem senha, auth Bearer com `SERVICE_TOKEN`, compose apenas em dev, endpoint no `identity_api`, imagem mínima em `client/`, sem tabela, idempotência por label, rede por app, porta aleatória com bind `0.0.0.0`.
- Fora de escopo: #54, #59, #60, #106, deploy de produção, TLS no gRPC.
- Nenhum commit/push/PR antes da aprovação explícita.
