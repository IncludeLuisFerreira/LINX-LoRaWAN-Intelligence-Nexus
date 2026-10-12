# Design: Nickname de device e gráfico multi-linha no dashboard

Data: 2026-10-12
Status: aguardando revisão do spec

## Contexto

Hoje um device é identificado apenas pelo `dev_eui`, um valor hexadecimal que
não é legível por humanos. Ao provisionar vários sensores na mesma aplicação,
o operador não consegue distinguir qual `dev_eui` corresponde a qual sensor
físico. Além disso, o dashboard de telemetria (Issue #42) exibe o histórico de
um único device por vez, sem uma visão consolidada da aplicação.

Esta mudança adiciona um campo `nickname` opcional ao device, permite editá-lo
após o cadastro, e adiciona ao dashboard um modo "Todos os devices" que
sobrepõe as séries de todos os devices da aplicação em um único gráfico
multi-linha.

## Objetivo

- Permitir identificar um sensor por um apelido legível no momento do cadastro.
- Permitir corrigir o apelido depois, sem recriar o device.
- Mostrar o apelido onde o device é listado e selecionado.
- Visualizar todas as séries de uma aplicação juntas, uma linha por device.

## Não-objetivos

- O `nickname` é metadado local do `identity_api`; ele **não** é enviado ao
  ChirpStack (o nome do device no ChirpStack continua `device-{dev_eui}`).
- Não há busca, ordenação ou filtro por `nickname`.
- Não há edição de outros campos do device (DevEUI, JoinEUI, AppKey, profile).
- Não há agregação por média nem bucketing temporal; o modo "Todos" é uma
  sobreposição de séries, não uma consolidação estatística.

## Decisões

- `nickname` é **opcional** (`nullable`). Se ausente, a UI usa o `dev_eui` como
  fallback.
- Limite de 50 caracteres, com `trim`; string vazia após `trim` vira `null`.
- Edição via novo `PATCH /api/v1/devices/{device_id}` que altera somente
  `nickname`.
- O gráfico unificado é **multi-linha** (uma linha por device), conforme
  escolha do usuário, não uma média.

## Arquitetura e componentes

### Backend — `identity_api` / `linx_shared`

**Modelo** (`linx_core/shared/src/linx_shared/models/device.py`)

Adicionar a coluna:

```python
nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

**Schemas** (`linx_core/shared/src/linx_shared/schemas/device.py`)

- `DeviceCreate`: adicionar `nickname: str | None = Field(default=None, max_length=50)`.
- `DeviceResponse`: adicionar `nickname: str | None`.
- Novo `DeviceUpdate` com `nickname: str | None = Field(default=None, max_length=50)`.
- Em `DeviceCreate` e `DeviceUpdate`, adicionar um `@field_validator("nickname")`
  dedicado (separado do `_normalize_hex`, que só trata EUIs) que aplica
  `strip()` e converte string vazia em `None`.

O `PATCH` usa `payload.model_dump(exclude_unset=True)` para distinguir
"campo não enviado" (não altera) de "campo enviado como `null`" (limpa o
apelido).

**Rotas** (`linx_core/services/identity_api/src/identity_api/routes/devices.py`)

- `create_device`: persistir `payload.nickname` no `Device`.
- Nova `update_device`:

```python
@router.patch("/devices/{device_id}", response_model=DeviceResponse)
def update_device(device_id: UUID, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Device not found!")
    data = payload.model_dump(exclude_unset=True)
    if "nickname" in data:
        device.nickname = data["nickname"]
    db.commit()
    db.refresh(device)
    return device
```

O `PATCH` não chama o ChirpStack.

**Migration** (`linx_core/services/identity_api/migrations/versions/`)

Nova revisão `add_nickname_to_devices`, `down_revision = "4d78141706c0"`
(head atual). `upgrade` adiciona `nickname` `String(50)` nullable;
`downgrade` remove a coluna.

### Contrato / OpenAPI

- Regenerar `docs/openapi-stub.json` a partir de `app.openapi()`. O teste
  `tests/test_openapi.py::test_openapi_stub_file_matches_live_spec` compara o
  arquivo com o spec vivo, então ele precisa refletir `nickname` no
  `DeviceCreate`/`DeviceResponse`, o novo `DeviceUpdate` e o `PATCH`.
- `frontend/openapi-stub.yaml`: adicionar `nickname` em `DeviceCreate` e
  `DeviceResponse`, o schema `DeviceUpdate` e o path `PATCH /devices/{device_id}`.
  Validar com `npx @redocly/cli lint openapi-stub.yaml` (usado no CI).

### Frontend

**Serviço** (`frontend/src/services/device.ts`)

- `DeviceOutput` += `nickname: string | null`.
- `CreateDeviceInput` += `nickname?: string | null`.
- Novo `update(id: string, data: { nickname: string | null }): Promise<DeviceOutput>`
  chamando `api.patch('/devices/{id}', data)`.

**Mocks** (`frontend/src/mocks/handlers.ts`)

- `MockDevice` += `nickname`.
- `POST /devices` persiste `nickname` (normalizado: `trim` / vazio → `null`).
- Novo handler `PATCH */api/v1/devices/:device_id` que atualiza `nickname`,
  devolve o device ou 404.
- `GET /devices` devolve `nickname`.

**Onboarding** (`frontend/src/pages/onboarding/OnboardingWizard.tsx`)

Campo `nickname` opcional no passo 2 (Confirmar dados), com
`z.string().max(50).optional()`. No submit, aplicar `trim` e enviar
`undefined` quando vazio. O campo não entra na validação de avanço do passo 2.

**Tabelas de device**

- `DeviceListPage` e `ApplicationDetailPage`: nova coluna "Nickname" (exibe o
  valor ou `—`).
- Nova ação de edição (ícone `Edit`) que abre
  `frontend/src/pages/devices/DeviceNicknameModal.tsx`. O modal segue o padrão
  de `ApplicationFormModal` (`Modal` + `react-hook-form` + `zod`), salva via
  `deviceService.update`, fecha e dispara `reload` da lista.

**Dashboard** (`frontend/src/pages/dashboard/Dashboard.tsx`)

- Select de device: rótulo `nickname ?? dev_eui`; nova opção "Todos os
  devices" (`value = '__all__'`).
- Device único: comportamento atual (uma série).
- "Todos": busca o histórico de cada device com `Promise.all`, gera uma série
  por device via `buildSeries` (rótulo `nickname ?? dev_eui`) e passa todas ao
  gráfico.
- Métrica: união das chaves numéricas dos payloads carregados.

**Serviço de telemetria** (`frontend/src/services/telemetry.ts`)

- Novo helper `mergeSeries(series: { key, label, data }[])` que produz linhas
  indexadas por `time`, com uma chave por device. Usado para alimentar o
  `recharts` com múltiplas linhas.

**Gráfico** (`frontend/src/components/charts/TelemetryLineChart.tsx`)

Generalizar para receber `series: { key: string; label: string; data: TelemetryPoint[] }[]`.
Renderiza um `<Line>` por série sobre as linhas mescladas, com `connectNulls`,
paleta de cores e `Legend`. O caso de um único device continua sendo uma
série. O prop `width` (usado em testes para render determinístico) é mantido.

## Fluxo de dados

1. Operador cadastra o device no onboarding e informa o apelido (opcional).
2. `POST /api/v1/devices` grava `nickname` no `identity_api`.
3. O apelido aparece nas tabelas e no select do dashboard.
4. Operador pode editar o apelido: `PATCH /api/v1/devices/{id}`.
5. No dashboard, ao escolher "Todos", o front busca o histórico REST de cada
   device e sobrepõe as séries no mesmo gráfico.

## Tratamento de erros

- `PATCH` de device inexistente → `404 {"detail": "Device not found!"}`.
- `nickname` com mais de 50 caracteres → `422` (validação Pydantic).
- Falha de rede na edição → `Alert` de erro no modal, sem fechar.
- Falha ao buscar histórico de um device no modo "Todos": a série daquele
  device é omitida; as demais continuam. Se todas falharem, exibe o `Alert`
  de erro com retry (comportamento atual do dashboard).

## Testes

Meta: cobertura ≥ 70% do código novo/alterado.

**Backend** (`linx_core/services/identity_api/tests/test_devices.py`)

- `POST` com `nickname` → 201 e corpo com o valor.
- `POST` sem `nickname` → `nickname` nulo.
- `POST` com `nickname` só de espaços / vazio → `null`.
- `PATCH` altera o `nickname` → 200 com valor novo.
- `PATCH` com `nickname: null` limpa o valor.
- `PATCH` de device inexistente → 404.
- `PATCH` com `nickname` > 50 → 422.
- `tests/test_openapi.py` continua passando após regenerar o stub.

**Frontend**

- `services/device.test.ts`: `update` chama `PATCH /devices/{id}` com o payload.
- `mocks/handlers.test.ts`: handler `PATCH` atualiza e devolve; 404 para id
  inexistente.
- `OnboardingWizard.test.tsx`: envio inclui `nickname`.
- `Dashboard.test.tsx`: modo "Todos" busca todos os devices e renderiza o
  gráfico multi-linha; select mostra `nickname`.
- `DeviceListPage.test.tsx` / `ApplicationDetailPage.test.tsx`: renderiza o
  nickname e o modal edita com sucesso.

**Verificação**

- `pytest` no `identity_api` (usa `.venv` local).
- `npm test` / `npm run test:coverage`, `npm run lint`, `npm run build`.
- `npx @redocly/cli lint frontend/openapi-stub.yaml`.

## Impacto e riscos

- `docs/openapi-stub.json` deve ser regenerado, senão o teste de contrato
  quebra (a lição veio da Issue #42).
- `DeviceResponse` ganha um campo; consumidores que validam schema estrito
  precisam tolerar `nickname`.
- O modo "Todos" faz N requisições REST (uma por device). Para aplicações com
  muitos devices isso pode ser custoso; aceitável neste escopo e endereçável
  depois com um endpoint agregado.
- Migração aditiva e nullable: sem downtime e sem backfill obrigatório.
