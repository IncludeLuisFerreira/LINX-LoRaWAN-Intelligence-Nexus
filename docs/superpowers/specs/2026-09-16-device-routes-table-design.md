# Design: tabela `device_routes` (dev_eui, app_id, agent_endpoint)

**Data:** 2026-09-16
**Escopo:** model SQLAlchemy + migration Alembic + testes + documentação
**Relacionado:** issue #33 / Sprint 2 (Aluno 2) / RF-013

## Contexto

O SaaS Backend precisa mapear `dev_eui` → `app_id` → `agent_endpoint` para
rotear a telemetria de cada dispositivo ao contêiner isolado da sua respectiva
aplicação (RF-013). Hoje existem os models `Tenant`, `Application`, `User` e
`TenantUser` (`saas_backend/src/linx/models/`), registrados em
`models/__init__.py` e `db/base.py`, com uma única migration inicial
(`0c14cfa628c3`).

O snippet da issue sugere `ForeignKey("applications.id")`, mas a tabela real do
model `Application` é `application` (singular). O FK correto é
`application.id`.

Há um `device_route.py` incompleto no working tree (sem uso), que será
sobrescrito. O move de `docs/plano_issues_github.md` para
`docs/superpowers/plans/` é uma mudança pré-existente **fora do escopo** desta
issue e não será commitado.

## Objetivo

Criar a tabela `device_routes` com `dev_eui` (UNIQUE + índice), `app_id` (FK
para `application.id`) e `agent_endpoint` (nullable), aplicada via migration
Alembic, coberta por testes e documentada.

## Não-objetivos

- Endpoint REST ou serviço de roteamento (issues #47/#63).
- Provisionamento do contêiner / atualização do endpoint real.
- Autenticação, validação de payload ou integração MQTT.
- Alterar as tabelas existentes além do relationship em `Application`.

## Design

### `saas_backend/src/linx/models/device_route.py`

Model `DeviceRoute` (classe singular, seguindo `Application`/`Tenant`) com
tabela `device_routes` (plural, conforme issue e `SPRINTS_BACKLOG.md`):

| Coluna           | Tipo                   | Restrições                                  |
| ---------------- | ---------------------- | ------------------------------------------- |
| `id`             | `UUID(as_uuid=True)`   | PK, `default=uuid.uuid4`                    |
| `dev_eui`        | `String(16)`           | `unique=True`, `index=True`, `nullable=False` |
| `app_id`         | `UUID(as_uuid=True)`   | FK `application.id` `ondelete="CASCADE"`, `nullable=False` |
| `agent_endpoint` | `String(255)`          | `Mapped[str \| None]`, `nullable=True`      |
| `created_at`     | `DateTime(timezone=True)` | `default=now(utc)`, `nullable=False`     |
| `updated_at`     | `DateTime(timezone=True)` | `default`/`onupdate=now(utc)`, `nullable=False` |

Relationship `application: Mapped["Application"]` com
`back_populates="device_routes"`.

### `saas_backend/src/linx/models/application.py`

Adiciona `device_routes: Mapped[list["DeviceRoute"]]` com
`back_populates="application"` e `cascade="all, delete-orphan"`, além do import
sob `TYPE_CHECKING`.

### Registro

Importar `DeviceRoute` em `models/__init__.py` (com `__all__`) e em
`db/base.py`, para que `Base.metadata` e o autogenerate do Alembic enxerguem a
tabela.

### Migration

`poetry run alembic revision --autogenerate -m "add device_routes table"` e
`poetry run alembic upgrade head`. Resultado esperado no Postgres: tabela
`device_routes` com as colunas, unique constraint e índice em `dev_eui` e FK
para `application.id`.

## Testes

- **`tests/test_models.py`** (atualizado):
  - incluir `DeviceRoute` em `test_all_tables_registered` e
    `test_models_have_uuid_pk`;
  - `test_db_base_import_registers_models` passa a esperar
    `['application', 'device_routes', 'tenant', 'tenant_user', 'user']`;
  - novos testes: `dev_eui` UNIQUE + indexado; FK `application.id`;
    relationship `DeviceRoute.application` ↔ `Application.device_routes`.
- **`tests/test_device_routes_schema.py`** (novo): usa
  `sqlalchemy.inspect(engine)` para validar no banco real as colunas
  `dev_eui`/`app_id`/`agent_endpoint`, a unique constraint e o índice em
  `dev_eui` e a FK para `application.id` — provando que a migration foi
  aplicada.
- Lint/typecheck: `black --check`, `isort --check`, `mypy`, `flake8`.

## Documentação

- `saas_backend/README.md`: incluir `device_routes` na lista de models, na
  tabela de models e na saída de verificação.
- `PROGRESS.md`: marcar a issue `#33` como concluída.
- `SPRINTS_BACKLOG.md`: marcar o item `device_routes` do Sprint 2.

## Commits

1. `feat(backend): adiciona model DeviceRoute e migration device_routes`
2. `test(backend): cobre metadata e schema da tabela device_routes`
3. `docs(backend): documenta a tabela device_routes`

## Validação

- `pytest` verde (baseline atual: 72 testes) incluindo os novos testes.
- `alembic current` = nova revisão (head); `alembic upgrade head` sem erro.
- Consulta no Postgres mostrando as colunas, o índice e a unique em `dev_eui`.
- `black`/`isort`/`mypy`/`flake8` sem erros.

## Riscos e mitigações

- **FK divergente (`applications` vs `application`):** usar `application.id`;
  teste de metadata cobre o alvo.
- **Autogenerate detectar drift de outros models:** revisar a migration gerada
  e mantê-la restrita a `device_routes`.
- **`agent_endpoint` nullable com typing `Mapped[str]`:** usar
  `Mapped[str | None]` para coerência entre tipo e nullability.
