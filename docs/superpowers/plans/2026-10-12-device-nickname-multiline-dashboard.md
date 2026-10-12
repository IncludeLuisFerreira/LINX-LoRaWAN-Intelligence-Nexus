# Device Nickname and Multi-line Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um campo `nickname` opcional (editável) ao device e um modo "Todos os devices" no dashboard que sobrepõe as séries de telemetria em um gráfico multi-linha.

**Architecture:** O `identity_api` ganha uma coluna nullable `nickname` em `devices`, exposta em `DeviceCreate`/`DeviceResponse` e editável por um novo `PATCH /api/v1/devices/{device_id}`. O frontend consome o campo nas tabelas, no onboarding e no select do dashboard; o `TelemetryLineChart` é generalizado para receber N séries e o dashboard busca o histórico de cada device quando "Todos os devices" é selecionado.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy / Alembic / Pydantic (backend); React 19 / TypeScript / Vite / Recharts 2 / React Hook Form + Zod / Vitest + Testing Library + MSW (frontend).

**Spec:** `docs/superpowers/specs/2026-10-12-device-nickname-multiline-dashboard-design.md`

## Global Constraints

- `nickname` é opcional (`nullable`), `String(50)`, `trim` aplicado; string vazia após `trim` vira `null`.
- O `PATCH` altera somente `nickname` e **não** chama o ChirpStack.
- Nova migration: `down_revision = "4d78141706c0"` (head atual).
- `docs/openapi-stub.json` DEVE ser regenerado; `tests/test_openapi.py::test_openapi_stub_file_matches_live_spec` compara o arquivo com `app.openapi()`.
- Frontend: cobertura mínima global 70% (`vitest.config.ts`).
- Formatação backend exigida pelo CI: `black`, `isort`, `flake8`, `mypy` limpos.
- CI de frontend valida `frontend/openapi-stub.yaml` com `npx @redocly/cli lint`.

## Review Focus

- `nickname` composto só de espaços ou string vazia deve persistir como `null` (a UI usa o `dev_eui` como fallback, nunca uma string em branco).
- `nickname` com exatamente 50 caracteres é aceito; 51 é rejeitado com 422.
- `PATCH` com `nickname: null` limpa o valor; `PATCH` sem o campo `nickname` não altera nada.
- No modo "Todos", se o histórico de um device falha, as outras séries continuam; se todos falham, exibe erro com retry.
- Device sem `nickname` mostra o `dev_eui` no select do dashboard e `—` nas tabelas.

---

### Task 1: Backend — coluna `nickname` e persistência no create

**Files:**
- Modify: `linx_core/shared/src/linx_shared/models/device.py`
- Modify: `linx_core/shared/src/linx_shared/schemas/device.py`
- Modify: `linx_core/services/identity_api/src/identity_api/routes/devices.py`
- Create: `linx_core/services/identity_api/migrations/versions/a1b2c3d4e5f6_add_nickname_to_devices.py`
- Test: `linx_core/services/identity_api/tests/test_devices.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Device.nickname: str | None`; `DeviceCreate.nickname: str | None`; `DeviceResponse.nickname: str | None`.

- [ ] **Step 1: Write the failing tests**

Em `tests/test_devices.py`, adicionar (o helper `_payload` aceita `**extra`):

```python
def _payload(app_id: str, dev_eui: str = "1122334455667788", **extra) -> dict:
    return {
        "dev_eui": dev_eui,
        "app_id": app_id,
        "join_eui": "0011223344556677",
        "app_key": "00112233445566778899aabbccddeeff",
        "device_profile_id": PROFILE_ID,
        **extra,
    }


def test_create_device_with_nickname(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="Sensor Galpão")
    )

    assert response.status_code == 201
    assert response.json()["nickname"] == "Sensor Galpão"


def test_create_device_without_nickname_is_null(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post("/api/v1/devices", json=_payload(app_id))

    assert response.status_code == 201
    assert response.json()["nickname"] is None


def test_create_device_blank_nickname_becomes_null(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="   ")
    )

    assert response.status_code == 201
    assert response.json()["nickname"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run (em `linx_core/services/identity_api`): `.venv/bin/python -m pytest tests/test_devices.py -q -k nickname`
Expected: FAIL (coluna/schema inexistente ou `nickname` ausente na resposta).

- [ ] **Step 3: Add the model column**

Em `linx_shared/models/device.py`, após `app_key`:

```python
nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

- [ ] **Step 4: Add schema fields and validator**

Em `linx_shared/schemas/device.py`:

```python
class DeviceCreate(BaseModel):
    dev_eui: str = Field(pattern=_HEX16)
    app_id: UUID
    join_eui: str = Field(pattern=_HEX16)
    app_key: str = Field(pattern=_HEX32)
    device_profile_id: UUID
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("dev_eui", "join_eui", "app_key")
    @classmethod
    def _normalize_hex(cls, value: str) -> str:
        return value.lower()

    @field_validator("nickname")
    @classmethod
    def _normalize_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dev_eui: str
    app_id: UUID
    join_eui: str
    device_profile_id: UUID
    nickname: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 5: Persist nickname in the route**

Em `routes/devices.py`, no `Device(...)` do `create_device`, adicionar:

```python
nickname=payload.nickname,
```

- [ ] **Step 6: Create the migration**

Criar `a1b2c3d4e5f6_add_nickname_to_devices.py` com cabeçalho
`revision = "a1b2c3d4e5f6"`, `down_revision = "4d78141706c0"` e:

```python
def upgrade() -> None:
    op.add_column(
        "devices", sa.Column("nickname", sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("devices", "nickname")
```

Aplicar: `.venv/bin/alembic -c ../../alembic.ini upgrade head`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_devices.py -q -k nickname`
Expected: PASS (3 passed).

- [ ] **Step 8: Commit**

```bash
git add linx_core/shared/src/linx_shared/models/device.py \
  linx_core/shared/src/linx_shared/schemas/device.py \
  linx_core/services/identity_api/src/identity_api/routes/devices.py \
  linx_core/services/identity_api/migrations/versions \
  linx_core/services/identity_api/tests/test_devices.py
git commit -m "feat(identity_api): adiciona nickname opcional ao device"
```

---

### Task 2: Backend — `PATCH /api/v1/devices/{device_id}`

**Files:**
- Modify: `linx_core/shared/src/linx_shared/schemas/device.py`
- Modify: `linx_core/services/identity_api/src/identity_api/routes/devices.py`
- Test: `linx_core/services/identity_api/tests/test_devices.py`

**Interfaces:**
- Consumes: `Device.nickname` (Task 1), `DeviceResponse`.
- Produces: `DeviceUpdate`; rota `update_device(device_id: UUID, payload: DeviceUpdate, db: Session) -> Device`.

- [ ] **Step 1: Write the failing tests**

```python
def test_update_device_nickname(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": "Bomba 1"}
    )

    assert response.status_code == 200
    assert response.json()["nickname"] == "Bomba 1"


def test_update_device_clears_nickname_with_null(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="Bomba 1")
    ).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": None}
    )

    assert response.status_code == 200
    assert response.json()["nickname"] is None


def test_update_device_without_nickname_leaves_it_unchanged(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post(
        "/api/v1/devices", json=_payload(app_id, nickname="Bomba 1")
    ).json()

    response = client.patch(f"/api/v1/devices/{created['id']}", json={})

    assert response.status_code == 200
    assert response.json()["nickname"] == "Bomba 1"


def test_update_device_not_found_returns_404(chirpstack):
    response = client.patch(
        f"/api/v1/devices/{uuid4()}", json={"nickname": "x"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found!"}


def test_update_device_nickname_too_long_returns_422(chirpstack):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)
    created = client.post("/api/v1/devices", json=_payload(app_id)).json()

    response = client.patch(
        f"/api/v1/devices/{created['id']}", json={"nickname": "a" * 51}
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_devices.py -q -k update_device`
Expected: FAIL (404, pois a rota não existe).

- [ ] **Step 3: Add the `DeviceUpdate` schema**

Em `linx_shared/schemas/device.py`:

```python
class DeviceUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)

    @field_validator("nickname")
    @classmethod
    def _normalize_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
```

- [ ] **Step 4: Add the route**

Em `routes/devices.py`, importar `DeviceUpdate` e adicionar:

```python
@router.patch(
    "/devices/{device_id}",
    status_code=status.HTTP_200_OK,
    response_model=DeviceResponse,
)
def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found!",
        )
    data = payload.model_dump(exclude_unset=True)
    if "nickname" in data:
        device.nickname = data["nickname"]
    db.commit()
    db.refresh(device)
    return device
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_devices.py -q`
Expected: PASS.

- [ ] **Step 6: Run backend lint/type checks**

Run (em `linx_core/services/identity_api`): `.venv/bin/black src tests && .venv/bin/isort src tests && .venv/bin/flake8 src tests && .venv/bin/mypy src tests`
Expected: sem erros.

- [ ] **Step 7: Commit**

```bash
git add linx_core/shared/src/linx_shared/schemas/device.py \
  linx_core/services/identity_api/src/identity_api/routes/devices.py \
  linx_core/services/identity_api/tests/test_devices.py
git commit -m "feat(identity_api): adiciona PATCH de nickname do device"
```

---

### Task 3: Backend — regenerar o stub OpenAPI

**Files:**
- Modify: `docs/openapi-stub.json`
- Test: `linx_core/services/identity_api/tests/test_openapi.py`

**Interfaces:**
- Consumes: rotas e schemas das Tasks 1–2.
- Produces: `docs/openapi-stub.json` idêntico a `app.openapi()`.

- [ ] **Step 1: Confirm the contract test currently fails**

Run (em `linx_core/services/identity_api`): `.venv/bin/python -m pytest tests/test_openapi.py -q`
Expected: FAIL em `test_openapi_stub_file_matches_live_spec` (o stub não tem `nickname`/`PATCH`).

- [ ] **Step 2: Regenerate the stub**

Run (em `linx_core/services/identity_api`):

```bash
.venv/bin/python -c "import json; from identity_api.main import app; print(json.dumps(app.openapi(), indent=2))" > ../../../docs/openapi-stub.json
```

- [ ] **Step 3: Run the contract test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_openapi.py -q`
Expected: PASS (4 passed).

- [ ] **Step 4: Commit**

```bash
git add docs/openapi-stub.json
git commit -m "docs: regenera openapi-stub com nickname do device"
```

---

### Task 4: Frontend — serviço de device e mocks

**Files:**
- Modify: `frontend/src/services/device.ts`
- Modify: `frontend/src/mocks/handlers.ts`
- Test: `frontend/src/services/device.test.ts`
- Test: `frontend/src/mocks/handlers.test.ts`

**Interfaces:**
- Consumes: `api` (axios).
- Produces: `DeviceOutput.nickname: string | null`; `CreateDeviceInput.nickname?: string | null`; `deviceService.update(id: string, data: { nickname: string | null }): Promise<DeviceOutput>`.

- [ ] **Step 1: Write the failing service test**

Em `services/device.test.ts`:

```ts
it('updates a device nickname with PATCH /devices/{id}', async () => {
  mocked.patch.mockResolvedValue({ data: { id: 'd1', nickname: 'Bomba 1' } });

  await deviceService.update('d1', { nickname: 'Bomba 1' });

  expect(mocked.patch).toHaveBeenCalledWith('/devices/d1', {
    nickname: 'Bomba 1',
  });
});
```

- [ ] **Step 2: Write the failing mock tests**

Em `mocks/handlers.test.ts`, adicionar um bloco `describe('device nickname handlers', ...)`:

```ts
it('stores nickname on create and returns it', async () => {
  const appId = await firstAppId();
  const res = await post(
    `${base}/devices`,
    { ...validDevice(appId, 'aabbccddeeff1001'), nickname: 'Sensor A' },
  );
  const body = (await res.json()) as { nickname: string | null };
  expect(body.nickname).toBe('Sensor A');
});

it('updates nickname via PATCH and returns the device', async () => {
  const appId = await firstAppId();
  const created = (await (
    await post(`${base}/devices`, validDevice(appId, 'aabbccddeeff1002'))
  ).json()) as { id: string };

  const res = await fetch(`${base}/devices/${created.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname: 'Novo' }),
  });

  expect(res.status).toBe(200);
  expect((await res.json()).nickname).toBe('Novo');
});

it('returns 404 when patching an unknown device', async () => {
  const res = await fetch(`${base}/devices/${crypto.randomUUID()}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname: 'x' }),
  });
  expect(res.status).toBe(404);
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run (em `frontend`): `npx vitest run src/services/device.test.ts src/mocks/handlers.test.ts`
Expected: FAIL (`update` inexistente; mock sem `nickname`/PATCH).

- [ ] **Step 4: Update the service**

Em `services/device.ts`:

```ts
export interface DeviceOutput {
  id: string;
  dev_eui: string;
  app_id: string;
  join_eui: string;
  device_profile_id: string;
  nickname: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateDeviceInput {
  dev_eui: string;
  app_id: string;
  join_eui: string;
  app_key: string;
  device_profile_id: string;
  nickname?: string | null;
}
```

E no objeto `deviceService`:

```ts
update: async (
  id: string,
  data: { nickname: string | null },
): Promise<DeviceOutput> => {
  const response = await api.patch<DeviceOutput>(`/devices/${id}`, data);
  return response.data;
},
```

- [ ] **Step 5: Update the mocks**

Em `mocks/handlers.ts`: adicionar `nickname: string | null` a `MockDevice`; no `POST`, definir
`nickname: body.nickname && body.nickname.trim() ? body.nickname.trim() : null`; adicionar:

```ts
http.patch('*/api/v1/devices/:device_id', async ({ params, request }) => {
  const index = mockDevices.findIndex(
    (device) => device.id === String(params.device_id),
  );
  if (index === -1) {
    return HttpResponse.json({ detail: 'Device not found!' }, { status: 404 });
  }
  const body = (await request.json()) as { nickname?: string | null };
  if ('nickname' in body) {
    mockDevices[index].nickname = body.nickname?.trim()
      ? body.nickname.trim()
      : null;
  }
  mockDevices[index].updated_at = now();
  return HttpResponse.json(mockDevices[index]);
}),
```

O `body` do `POST` passa a tipar `nickname?: string`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx vitest run src/services/device.test.ts src/mocks/handlers.test.ts`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/services/device.ts frontend/src/services/device.test.ts \
  frontend/src/mocks/handlers.ts frontend/src/mocks/handlers.test.ts
git commit -m "feat(frontend): nickname no serviço e mocks de device"
```

---

### Task 5: Frontend — nickname no onboarding

**Files:**
- Modify: `frontend/src/pages/onboarding/OnboardingWizard.tsx`
- Test: `frontend/src/pages/onboarding/OnboardingWizard.test.tsx`

**Interfaces:**
- Consumes: `deviceService.create` com `nickname` (Task 4).
- Produces: campo de formulário `nickname`.

- [ ] **Step 1: Write the failing test**

```ts
it('submits the device nickname when provided', async () => {
  const appId = await firstAppId();
  await decodeToStep2();

  await userEvent.type(
    screen.getByLabelText('Nickname (opcional)'),
    'Sensor Galpão',
  );
  await goToStep3();
  await userEvent.selectOptions(
    await screen.findByLabelText('Aplicação'),
    appId,
  );
  await screen.findByRole('option', { name: 'Perfil Teste' });

  await userEvent.click(
    screen.getByRole('button', { name: 'Cadastrar device' }),
  );
  await screen.findByText('devices-page');

  const devices = (await (
    await fetch(`${base}/devices?app_id=${appId}`)
  ).json()) as { dev_eui: string; nickname: string | null }[];
  const device = devices.find((d) => d.dev_eui === 'aabbccddeeff0011');
  expect(device?.nickname).toBe('Sensor Galpão');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/pages/onboarding/OnboardingWizard.test.tsx -t "nickname"`
Expected: FAIL (label inexistente).

- [ ] **Step 3: Add the field**

Em `OnboardingWizard.tsx`: adicionar ao `schema`
`nickname: z.string().max(50, 'Máximo de 50 caracteres').optional()`; adicionar
`nickname: ''` aos `defaultValues`; no passo 2, após o `Input` de `AppKey`, adicionar:

```tsx
<Input
  label="Nickname (opcional)"
  placeholder="Ex: Sensor Galpão"
  error={errors.nickname?.message}
  {...register('nickname')}
/>
```

No `submit`, incluir:

```ts
nickname: values.nickname?.trim() ? values.nickname.trim() : undefined,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/pages/onboarding/OnboardingWizard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/onboarding/OnboardingWizard.tsx \
  frontend/src/pages/onboarding/OnboardingWizard.test.tsx
git commit -m "feat(frontend): campo de nickname no onboarding"
```

---

### Task 6: Frontend — nickname nas tabelas e modal de edição

**Files:**
- Create: `frontend/src/pages/devices/DeviceNicknameModal.tsx`
- Modify: `frontend/src/pages/devices/DeviceListPage.tsx`
- Modify: `frontend/src/pages/applications/ApplicationDetailPage.tsx`
- Test: `frontend/src/pages/devices/DeviceListPage.test.tsx`
- Test: `frontend/src/pages/applications/ApplicationDetailPage.test.tsx`

**Interfaces:**
- Consumes: `deviceService.update` (Task 4).
- Produces: `DeviceNicknameModal` com props `{ open: boolean; device: DeviceOutput | null; onClose: () => void; onSaved: () => void }`.

- [ ] **Step 1: Write the failing tests**

Em `DeviceListPage.test.tsx`:

```ts
it('shows the nickname and edits it from the table', async () => {
  const { appId } = await firstTenantAndApp();
  await fetch(`${base}/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dev_eui: 'aabbccddeeff0606',
      app_id: appId,
      join_eui: '1122334455667788',
      app_key: '00112233445566778899aabbccddeeff',
      device_profile_id: 'profile-test',
      nickname: 'Bomba 1',
    }),
  });

  renderPage();
  await screen.findByText('aabbccddeeff0606');
  expect(screen.getByText('Bomba 1')).toBeInTheDocument();

  await userEvent.click(
    screen.getByRole('button', { name: 'Editar nickname aabbccddeeff0606' }),
  );
  const input = await screen.findByLabelText('Nickname');
  await userEvent.clear(input);
  await userEvent.type(input, 'Bomba 2');
  await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

  expect(await screen.findByText('Bomba 2')).toBeInTheDocument();
});
```

Em `ApplicationDetailPage.test.tsx`, um teste análogo (renderize a página com a rota
`/tenants/:tenantId/applications/:appId`, crie um device com nickname e verifique a
coluna e a edição). Reuse o helper de setup já existente nesse arquivo.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/pages/devices/DeviceListPage.test.tsx src/pages/applications/ApplicationDetailPage.test.tsx`
Expected: FAIL (coluna/botão/modal inexistentes).

- [ ] **Step 3: Create the modal**

`frontend/src/pages/devices/DeviceNicknameModal.tsx` — padrão `ApplicationFormModal`
(`Modal` + `react-hook-form` + `zod`):

```tsx
const schema = z.object({
  nickname: z.string().max(50, 'Máximo de 50 caracteres').optional(),
});

interface DeviceNicknameModalProps {
  open: boolean;
  device: DeviceOutput | null;
  onClose: () => void;
  onSaved: () => void;
}
```

No `onSubmit`: chamar
`deviceService.update(device.id, { nickname: values.nickname?.trim() ? values.nickname.trim() : null })`;
em erro, `setError('root', { message: getErrorMessage(err) })`; em sucesso, `onSaved()`.
`useEffect` reseta o form com `device?.nickname ?? ''` quando `open`. Form `id="device-nickname-form"`,
`Input` label `"Nickname"`, footer `Cancelar` / `Salvar`.

- [ ] **Step 4: Wire the tables**

`DeviceListPage.tsx`: adicionar estado `editing: DeviceRow | null`; coluna
`{ key: 'nickname', header: 'Nickname', render: (row) => row.device.nickname ?? '—' }`;
botão de ação (ícone `Edit`) com `aria-label={`Editar nickname ${row.device.dev_eui}`}`
chamando `setEditing(row)`; renderizar
`<DeviceNicknameModal open={editing !== null} device={editing?.device ?? null} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />`.

`ApplicationDetailPage.tsx`: mesma coluna; estado `editingDevice: DeviceOutput | null`;
botão `aria-label={`Editar nickname ${device.dev_eui}`}`; modal com
`device={editingDevice}` e `onSaved={() => { setEditingDevice(null); reload(); }}`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run src/pages/devices/DeviceListPage.test.tsx src/pages/applications/ApplicationDetailPage.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/devices frontend/src/pages/applications
git commit -m "feat(frontend): nickname nas tabelas e modal de edição"
```

---

### Task 7: Frontend — gráfico multi-linha e modo "Todos os devices"

**Files:**
- Modify: `frontend/src/services/telemetry.ts`
- Modify: `frontend/src/components/charts/TelemetryLineChart.tsx`
- Modify: `frontend/src/pages/dashboard/Dashboard.tsx`
- Test: `frontend/src/services/telemetry.test.ts`
- Test: `frontend/src/components/charts/TelemetryLineChart.test.tsx`
- Test: `frontend/src/pages/dashboard/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `telemetryService.history`, `buildSeries`, `numericMetrics`, `DeviceOutput.nickname` (Task 4).
- Produces: `SeriesInput { key: string; label: string; data: TelemetryPoint[] }`; `mergeSeries(series: SeriesInput[]): Record<string, number | string>[]`; `TelemetryLineChart` com prop `series: SeriesInput[]`.

- [ ] **Step 1: Write the failing tests**

`telemetry.test.ts`:

```ts
describe('mergeSeries', () => {
  it('merges points by time with one key per series', () => {
    const rows = mergeSeries([
      { key: 'a', label: 'A', data: [{ time: 't1', value: 1 }] },
      { key: 'b', label: 'B', data: [{ time: 't1', value: 2 }, { time: 't2', value: 3 }] },
    ]);

    expect(rows).toEqual([
      { time: 't1', a: 1, b: 2 },
      { time: 't2', b: 3 },
    ]);
  });
});
```

`TelemetryLineChart.test.tsx` (substituir a prop `data` por `series`):

```ts
it('renders one line per series', () => {
  const { container } = render(
    <TelemetryLineChart
      series={[
        { key: 'a', label: 'A', data: [{ time: 't1', value: 1 }] },
        { key: 'b', label: 'B', data: [{ time: 't1', value: 2 }] },
      ]}
      width={800}
    />,
  );

  expect(container.querySelectorAll('.recharts-line-curve')).toHaveLength(2);
});
```

`Dashboard.test.tsx`:

```ts
it('overlays all devices when "Todos os devices" is selected', async () => {
  const appId = await firstAppId();
  await createDevice(appId, 'aabbccddeeff0707');
  await createDevice(appId, 'aabbccddeeff0808');

  const requested: (string | null)[] = [];
  server.use(
    http.get('*/api/v1/telemetry', ({ request }) => {
      requested.push(new URL(request.url).searchParams.get('dev_eui'));
      return HttpResponse.json({ items: [], next_cursor: null });
    }),
  );

  renderDashboard(appId);
  await screen.findByLabelText('Device');

  await userEvent.selectOptions(
    screen.getByLabelText('Device'),
    'Todos os devices',
  );

  await waitFor(() => {
    expect(requested).toContain('aabbccddeeff0707');
    expect(requested).toContain('aabbccddeeff0808');
  });
  expect(screen.getByTestId('telemetry-chart')).toBeInTheDocument();
});

it('shows the nickname as the device option label and dev_eui as fallback', async () => {
  const appId = await firstAppId();
  const create = (devEui: string, nickname?: string) =>
    fetch(`${base}/devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dev_eui: devEui,
        app_id: appId,
        join_eui: '1122334455667788',
        app_key: '00112233445566778899aabbccddeeff',
        device_profile_id: 'profile-test',
        nickname,
      }),
    });
  await create('aabbccddeeff0909', 'Sensor Sul');
  await create('aabbccddeeff0c0c');

  renderDashboard(appId);

  expect(
    await screen.findByRole('option', { name: 'Sensor Sul' }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('option', { name: 'aabbccddeeff0c0c' }),
  ).toBeInTheDocument();
});

it('keeps other series when one device history fails', async () => {
  const appId = await firstAppId();
  await createDevice(appId, 'aabbccddeeff0a0a');
  await createDevice(appId, 'aabbccddeeff0b0b');

  server.use(
    http.get('*/api/v1/telemetry', ({ request }) => {
      const devEui = new URL(request.url).searchParams.get('dev_eui');
      if (devEui === 'aabbccddeeff0a0a') {
        return HttpResponse.json({ detail: 'boom' }, { status: 500 });
      }
      return HttpResponse.json({
        items: [
          {
            time: '2026-01-01T00:00:00Z',
            dev_eui: devEui,
            payload: { temperature: 20 },
            rssi: -70,
            snr: 7,
            app_id: 'mock-app',
            event_type: 'up',
          },
        ],
        next_cursor: null,
      });
    }),
  );

  renderDashboard(appId);
  await screen.findByLabelText('Device');
  await userEvent.selectOptions(
    screen.getByLabelText('Device'),
    'Todos os devices',
  );

  expect(await screen.findByTestId('telemetry-chart')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/services/telemetry.test.ts src/components/charts/TelemetryLineChart.test.tsx src/pages/dashboard/Dashboard.test.tsx`
Expected: FAIL (`mergeSeries` inexistente; chart sem prop `series`; opção inexistente).

- [ ] **Step 3: Add `mergeSeries`**

Em `services/telemetry.ts`:

```ts
export interface SeriesInput {
  key: string;
  label: string;
  data: TelemetryPoint[];
}

export function mergeSeries(
  series: SeriesInput[],
): Record<string, number | string>[] {
  const rows = new Map<string, Record<string, number | string>>();
  for (const entry of series) {
    for (const point of entry.data) {
      const row = rows.get(point.time) ?? { time: point.time };
      row[entry.key] = point.value;
      rows.set(point.time, row);
    }
  }
  return [...rows.values()].sort(
    (a, b) =>
      new Date(String(a.time)).getTime() - new Date(String(b.time)).getTime(),
  );
}
```

- [ ] **Step 4: Generalize the chart**

Em `TelemetryLineChart.tsx`: props `{ series: SeriesInput[]; height?: number; width?: number }`.
`const rows = mergeSeries(series)`; renderizar um `<Line>` por série:

```tsx
{series.map((entry, index) => (
  <Line
    key={entry.key}
    type="monotone"
    dataKey={entry.key}
    name={entry.label}
    stroke={COLORS[index % COLORS.length]}
    strokeWidth={2}
    dot={false}
    connectNulls
    isAnimationActive={false}
  />
))}
```

Adicionar `<Legend />`. Manter `data-testid="telemetry-chart"` e o prop `width` (render direto em testes).

- [ ] **Step 5: Wire the dashboard**

Em `Dashboard.tsx`:
- `const ALL_DEVICES = '__all__';`
- helper local:

```ts
async function loadHistories(devices: DeviceOutput[]): Promise<TelemetryHistory[]> {
  const results = await Promise.allSettled(
    devices.map((device) => telemetryService.history(device.dev_eui)),
  );
  if (results.length > 0 && results.every((r) => r.status === 'rejected')) {
    throw (results[0] as PromiseRejectedResult).reason;
  }
  return results.map((r) =>
    r.status === 'fulfilled' ? r.value : EMPTY_HISTORY,
  );
}
```

- `useAsyncData` fn:

```ts
() => {
  if (activeDevEui === ALL_DEVICES) return loadHistories(devices);
  if (activeDevEui) return telemetryService.history(activeDevEui).then((h) => [h]);
  return Promise.resolve([] as TelemetryHistory[]);
},
[appId, activeDevEui, devices.length],
```

- `histories = history ?? []`; `allItems = histories.flatMap((h) => h.items)`;
  `metrics = numericMetrics(allItems)`; `activeMetric` como hoje.
- séries:

```ts
const chartSeries: SeriesInput[] =
  activeDevEui === ALL_DEVICES
    ? devices.map((device, index) => ({
        key: device.dev_eui,
        label: device.nickname ?? device.dev_eui,
        data: buildSeries(histories[index]?.items ?? [], activeMetric),
      }))
    : [
        {
          key: activeDevEui,
          label:
            devices.find((d) => d.dev_eui === activeDevEui)?.nickname ??
            activeDevEui,
          data: buildSeries(allItems, activeMetric),
        },
      ];
const hasData = chartSeries.some((entry) => entry.data.length > 0);
```

- Select de device: `options` = devices mapeados com label `nickname ?? dev_eui`
  mais `{ value: ALL_DEVICES, label: 'Todos os devices' }`.
- Renderizar `<TelemetryLineChart series={chartSeries} />` quando `hasData`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx vitest run src/services/telemetry.test.ts src/components/charts/TelemetryLineChart.test.tsx src/pages/dashboard/Dashboard.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/services/telemetry.ts frontend/src/services/telemetry.test.ts \
  frontend/src/components/charts frontend/src/pages/dashboard
git commit -m "feat(frontend): grafico multi-linha com todos os devices"
```

---

### Task 8: Documentação do frontend

**Files:**
- Modify: `frontend/README.md`
- Modify: `frontend/openapi-stub.yaml`

**Interfaces:**
- Consumes: contrato das Tasks 1–2, comportamento das Tasks 4–7.
- Produces: documentação.

- [ ] **Step 1: Update the README**

Em `frontend/README.md`:
- Tabela "API consumida": adicionar `PATCH /devices/{id}` (nickname) na linha de Device.
- Nova subseção "Nickname de device": campo opcional no onboarding, editável nas
  tabelas via modal, exibido como fallback `dev_eui` quando vazio.
- Na seção "Dashboard de Telemetria": documentar a opção "Todos os devices"
  (gráfico multi-linha, uma linha por device).

- [ ] **Step 2: Update the OpenAPI stub**

Em `frontend/openapi-stub.yaml`, adicionar:
- schema `DeviceResponse` (com `nickname: { type: string, nullable: true }`);
- schema `DeviceUpdate` (`nickname` string nullable, `maxLength: 50`);
- path `PATCH /devices/{device_id}` com param `device_id` (uuid), body `DeviceUpdate`,
  respostas `200` (`DeviceResponse`), `404`, `422`.

- [ ] **Step 3: Lint the stub**

Run (em `frontend`): `npx @redocly/cli lint openapi-stub.yaml`
Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git add frontend/README.md frontend/openapi-stub.yaml
git commit -m "docs(frontend): documenta nickname do device e dashboard multi-linha"
```

---

### Task 9: Verificação final

**Files:** nenhum (apenas execução).

- [ ] **Step 1: Backend**

Run (em `linx_core/services/identity_api`):
`.venv/bin/python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=70`
Expected: PASS, cobertura ≥ 70%.

- [ ] **Step 2: Backend lint**

Run: `.venv/bin/black --check src tests && .venv/bin/isort --check-only src tests && .venv/bin/flake8 src tests && .venv/bin/mypy src tests`
Expected: sem erros.

- [ ] **Step 3: Frontend**

Run (em `frontend`): `npm run lint && npm run build && npm run test:coverage`
Expected: lint limpo; build ok; testes PASS; cobertura ≥ 70%.

- [ ] **Step 4: Stub lint**

Run (em `frontend`): `npx @redocly/cli lint openapi-stub.yaml`
Expected: sem erros.
