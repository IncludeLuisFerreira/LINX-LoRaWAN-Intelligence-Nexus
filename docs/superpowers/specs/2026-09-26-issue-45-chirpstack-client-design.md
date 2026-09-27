# Design: cliente gRPC do ChirpStack (issue #45)

**Data:** 2026-09-26
**Issue:** [#45](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/45)
**Sprint:** 3
**Escopo:** cliente gRPC centralizando o acesso à API do ChirpStack v4 no SaaS Backend, com o método `create_device` (RF-022). Base para a #46 (provisionamento de devices) e para downlinks na S6 (#91).
**Relacionado:** #46 (POST /api/v1/devices), RF-022/RF-023 do PRD.

## Contexto

O SaaS Backend precisa criar dispositivos e enfileirar downlinks no Network
Server (ChirpStack v4), que expõe uma API gRPC (porta `8080` no `infra/`).
A issue pede um cliente `chirpstack-api` (`4.x`) com runtime `grpcio` (`1.x`),
centralizando esse acesso.

O corpo da issue aponta `saas_backend/src/linx/chirpstack_client.py`, caminho
que não existe na estrutura atual (monorepo Poetry de sub-pacotes). O serviço
REST do SaaS é o pacote `identity_api` (FastAPI) — `identity_api/src/identity_api/` —
e é ele quem usará o cliente na #46. Decisão: o cliente vive em `identity_api`,
seguindo o padrão de config já usado em `agent_bridge` (classe própria que
estende `linx_shared.core.config.Settings`).

## Objetivo

- `ChirpStackClient` com `create_device(device)` que chama
  `api.DeviceServiceStub.Create` autenticando via metadata
  `authorization: Bearer <token>`.
- Credenciais via env (`CHIRPSTACK_HOST`, `CHIRPSTACK_API_TOKEN`), nunca hardcoded.
- Canal gRPC injetável para permitir teste sem servidor real.

## Não-objetivos

- Endpoint `POST /api/v1/devices` (#46) — apenas o cliente.
- `enqueue` de downlinks (S6, #91).
- TLS/mTLS (Sprint 5) — hoje `insecure_channel`, como o restante da S2/S3.
- Retry/circuit breaker (Sprint 7).

## Componentes

### `identity_api/src/identity_api/chirpstack_client.py` (novo)

```python
import grpc
from chirpstack_api import api


class ChirpStackClient:
    def __init__(self, host, token, channel=None):
        self.host = host
        self.token = token
        self._channel = channel or grpc.insecure_channel(host)

    def _metadata(self):
        return [("authorization", f"Bearer {self.token}")]

    def create_device(self, device):
        stub = api.DeviceServiceStub(self._channel)
        request = api.CreateDeviceRequest(device=device)
        stub.Create(request, metadata=self._metadata())
```

- `channel` é o ponto de injeção para testes; quando omitido, o cliente monta um
  canal `insecure` para `host` (canais gRPC são lazy — nenhuma conexão ocorre na
  construção).
- `create_device` retorna `None` (o `Create` do ChirpStack retorna
  `google.protobuf.Empty`).

### `identity_api/src/identity_api/config.py` (novo)

- `ChirpStackSettings(Settings)` com `chirpstack_host: str = "localhost:8080"` e
  `chirpstack_api_token: str = ""` (mapeiam `CHIRPSTACK_HOST` /
  `CHIRPSTACK_API_TOKEN` via pydantic-settings).

### Dependências e env

- `identity_api/pyproject.toml`: `chirpstack-api = "^4.19.0"` (deps `grpcio`,
  `google-api-core`); override mypy ignorando `chirpstack_api` (sem stubs).
- `saas_backend/.env.example`: `CHIRPSTACK_HOST=localhost:8080` e
  `CHIRPSTACK_API_TOKEN=`.

## Erros

- Falha de RPC propaga `grpc.RpcError` naturalmente; o tratamento de erro/HTTP
  fica para a camada de rota na #46 (YAGNI nesta issue).

## Testes

- `identity_api/tests/test_chirpstack_client.py` (novo):
  - `create_device` propaga o `dev_eui` do device e a metadata
    `authorization: Bearer <token>` ao stub (com `DeviceServiceStub` mockado);
  - sem canal explícito, `grpc.insecure_channel` é chamado com `host`;
  - com canal explícito, `grpc.insecure_channel` não é chamado.
- Gate: `poetry -C identity_api run pytest` e lint/mypy/flake8 verdes.

## Verificação

1. `poetry -C identity_api run pytest -q` (suíte completa, inclui os 3 novos).
2. `poetry -C identity_api run black --check src/ tests/` e `mypy src/ tests/`.

## Decisões e riscos

- **Cliente mínimo (só `create_device`):** `enqueue` e demais RPCs entram quando
  forem necessários (S6) — YAGNI.
- **Localização:** `identity_api` em vez do caminho `src/linx/` citado na issue;
  é o serviço consumidor do cliente e segue a estrutura real do monorepo.
- **`insecure_channel`:** TLS/mTLS é escopo da Sprint 5; nesta etapa o token
  Bearer trafega em claro, consistente com o resto da S3.
