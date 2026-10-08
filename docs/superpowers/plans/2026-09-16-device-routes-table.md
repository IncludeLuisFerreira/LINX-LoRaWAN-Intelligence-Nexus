# device_routes table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a tabela `device_routes` (`dev_eui`, `app_id`, `agent_endpoint`) no SaaS Backend via model SQLAlchemy 2.0 e migration Alembic, com testes e documentação.

**Architecture:** Model `DeviceRoute` (classe singular, tabela plural) em `src/linx/models/`, com relationship bidirecional com `Application`, registrado em `models/__init__.py` e `db/base.py`. Migration autogerada e aplicada no Postgres local. Testes de metadata (SQLAlchemy) e de schema (introspecção do banco).

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, PostgreSQL 15, pytest, poetry, taskipy.

**Spec:** `docs/superpowers/specs/2026-09-16-device-routes-table-design.md`

**Branch:** `issue33_devices_routes` (já ativa)

**Baseline:** 72 testes passando (`cd saas_backend && poetry run pytest -q`); migration head `0c14cfa628c3`.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
| ------- | ---- | ---------------- |
| `saas_backend/src/linx/models/device_route.py` | Criar (sobrescrever) | Model `DeviceRoute` / tabela `device_routes`. |
| `saas_backend/src/linx/models/application.py` | Modificar | Adicionar relationship `device_routes`. |
| `saas_backend/src/linx/models/__init__.py` | Modificar | Exportar `DeviceRoute`. |
| `saas_backend/src/linx/db/base.py` | Modificar | Registrar `DeviceRoute` no metadata. |
| `saas_backend/migrations/versions/<rev>_add_device_routes_table.py` | Criar (autogenerate) | Migration da tabela. |
| `saas_backend/tests/test_models.py` | Modificar | Testes de metadata/relacionamento. |
| `saas_backend/tests/test_device_routes_schema.py` | Criar | Teste de schema aplicado no Postgres. |
| `saas_backend/README.md` | Modificar | Documentar model/tabela. |
| `PROGRESS.md` | Modificar | Marcar #33 concluída. |
| `SPRINTS_BACKLOG.md` | Modificar | Marcar item do Sprint 2. |

**Fora do escopo (não commitar):** move pré-existente `docs/plano_issues_github.md` → `docs/superpowers/plans/plano_issues_github.md`.

Todos os comandos rodam a partir de `saas_backend/`, salvo indicado.

---

## Task 1: Testes de metadata do `DeviceRoute` (TDD — falham primeiro)

**Files:**
- Modify: `saas_backend/tests/test_models.py`

- [ ] **Step 1: Atualizar imports e conjuntos esperados**

Em `saas_backend/tests/test_models.py`, substituir a linha de import:

```python
from linx.models import Application, Base, Tenant, TenantUser, User
```

por:

```python
from linx.models import (
    Application,
    Base,
    DeviceRoute,
    Tenant,
    TenantUser,
    User,
)
```

- [ ] **Step 2: Atualizar `test_all_tables_registered`**

Substituir o corpo do teste para incluir `device_routes`:

```python
def test_all_tables_registered():
    assert set(Base.metadata.tables) == {
        "application",
        "device_routes",
        "tenant",
        "tenant_user",
        "user",
    }
```

- [ ] **Step 3: Incluir `DeviceRoute` em `test_models_have_uuid_pk`**

Substituir a linha do loop:

```python
    for model in (Tenant, Application, User):
```

por:

```python
    for model in (Tenant, Application, User, DeviceRoute):
```

- [ ] **Step 4: Adicionar testes de coluna/FK/relationship**

Após `test_application_tenant_foreign_key`, adicionar:

```python
def test_device_route_dev_eui_is_unique_and_indexed():
    column = DeviceRoute.__table__.c.dev_eui
    assert column.unique is True
    assert column.index is True


def test_device_route_application_foreign_key():
    fk = list(DeviceRoute.__table__.foreign_keys)[0]
    assert fk.target_fullname == "application.id"


def test_device_route_application_relationship():
    assert DeviceRoute.application.property.mapper.class_ is Application
    assert Application.device_routes.property.mapper.class_ is DeviceRoute
```

- [ ] **Step 5: Atualizar `test_db_base_import_registers_models`**

Substituir a linha `expected = ...` por:

```python
    expected = "['application', 'device_routes', 'tenant', 'tenant_user', 'user']"
```

- [ ] **Step 6: Rodar os testes para confirmar que falham**

Run: `cd saas_backend && poetry run pytest tests/test_models.py -q`
Expected: FAIL na coleta com `ImportError: cannot import name 'DeviceRoute'`.

---

## Task 2: Implementar o model e o relationship

**Files:**
- Create: `saas_backend/src/linx/models/device_route.py`
- Modify: `saas_backend/src/linx/models/application.py`
- Modify: `saas_backend/src/linx/models/__init__.py`
- Modify: `saas_backend/src/linx/db/base.py`

- [ ] **Step 1: Criar `device_route.py` (sobrescrevendo o arquivo incompleto)**

Conteúdo completo de `saas_backend/src/linx/models/device_route.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from linx.db.base_class import Base

if TYPE_CHECKING:
    from linx.models.application import Application


class DeviceRoute(Base):
    """Mapeia um dev_eui para a aplicação e o endpoint do Client Agent."""

    __tablename__ = "device_routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    dev_eui: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        index=True,
        nullable=False,
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application.id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_endpoint: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    application: Mapped["Application"] = relationship(
        back_populates="device_routes"
    )
```

- [ ] **Step 2: Adicionar o relationship em `application.py`**

Em `saas_backend/src/linx/models/application.py`, substituir o bloco `if TYPE_CHECKING:`:

```python
if TYPE_CHECKING:
    from linx.models.tenant import Tenant
```

por:

```python
if TYPE_CHECKING:
    from linx.models.device_route import DeviceRoute
    from linx.models.tenant import Tenant
```

E adicionar ao final da classe `Application` (após `tenant`):

```python
    device_routes: Mapped[list["DeviceRoute"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 3: Exportar em `models/__init__.py`**

Substituir todo o conteúdo de `saas_backend/src/linx/models/__init__.py` por:

```python
from linx.db.base_class import Base
from linx.models.application import Application
from linx.models.device_route import DeviceRoute
from linx.models.tenant import Tenant
from linx.models.tenant_user import TenantUser
from linx.models.user import User

__all__ = [
    "Base",
    "Tenant",
    "Application",
    "User",
    "TenantUser",
    "DeviceRoute",
]
```

- [ ] **Step 4: Registrar em `db/base.py`**

Em `saas_backend/src/linx/db/base.py`, adicionar o import após o de `Application`:

```python
from linx.models.device_route import DeviceRoute  # noqa: F401
```

- [ ] **Step 5: Rodar os testes de metadata**

Run: `cd saas_backend && poetry run pytest tests/test_models.py -q`
Expected: PASS (todos os testes de `test_models.py`).

---

## Task 3: Gerar e aplicar a migration Alembic

**Files:**
- Create: `saas_backend/migrations/versions/<rev>_add_device_routes_table.py`

- [ ] **Step 1: Gerar a migration**

Run: `cd saas_backend && poetry run alembic revision --autogenerate -m "add device_routes table"`
Expected: `Generating .../migrations/versions/<rev>_add_device_routes_table.py ... done`.

- [ ] **Step 2: Revisar a migration gerada**

Abrir o arquivo criado e confirmar que contém **apenas** a tabela `device_routes` (sem drift de outras tabelas). O conteúdo esperado é:

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "device_routes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("dev_eui", sa.String(length=16), nullable=False),
        sa.Column("app_id", sa.UUID(), nullable=False),
        sa.Column("agent_endpoint", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["app_id"], ["application.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_device_routes_dev_eui"),
        "device_routes",
        ["dev_eui"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_device_routes_dev_eui"), table_name="device_routes"
    )
    op.drop_table("device_routes")
```

Se houver comandos extras, remover e ajustar `down_revision` para `"0c14cfa628c3"` caso necessário.

- [ ] **Step 3: Aplicar a migration**

Run: `cd saas_backend && poetry run alembic upgrade head`
Expected: `Running upgrade 0c14cfa628c3 -> <rev>, add device_routes table`.

- [ ] **Step 4: Confirmar a revisão aplicada**

Run: `cd saas_backend && poetry run alembic current`
Expected: `<rev> (head)`.

- [ ] **Step 5: Verificar o schema no Postgres**

Run:
```bash
docker exec infra-postgres-1 psql -U linx -d linx -c "\d device_routes"
```
Expected: 6 colunas (`id`, `dev_eui`, `app_id`, `agent_endpoint`, `created_at`, `updated_at`), `UNIQUE`/índice `ix_device_routes_dev_eui` e FK `app_id → application(id)`.

> Se o comando `psql`/usuário não existir no container, use `poetry run python` com `sqlalchemy.inspect(engine)` (o teste da Task 4 cobre isso).

---

## Task 4: Commit da feature + testes de metadata

- [ ] **Step 1: Rodar a suíte completa**

Run: `cd saas_backend && poetry run pytest -q`
Expected: PASS (72 + novos testes).

- [ ] **Step 2: Commit**

```bash
git add saas_backend/src/linx/models/device_route.py \
        saas_backend/src/linx/models/application.py \
        saas_backend/src/linx/models/__init__.py \
        saas_backend/src/linx/db/base.py \
        saas_backend/migrations/versions/ \
        saas_backend/tests/test_models.py
git commit -m "feat(backend): adiciona model DeviceRoute e migration device_routes"
```

> Nota: os testes de metadata vão neste commit junto da feature (TDD). O commit seguinte cobre o schema aplicado no banco.

---

## Task 5: Teste de schema aplicado no Postgres

**Files:**
- Create: `saas_backend/tests/test_device_routes_schema.py`

- [ ] **Step 1: Criar o teste**

Conteúdo completo de `saas_backend/tests/test_device_routes_schema.py`:

```python
from sqlalchemy import inspect

from linx.db.base import engine


def test_device_routes_table_has_expected_columns():
    columns = {
        column["name"] for column in inspect(engine).get_columns("device_routes")
    }
    assert {
        "id",
        "dev_eui",
        "app_id",
        "agent_endpoint",
        "created_at",
        "updated_at",
    } <= columns


def test_device_routes_dev_eui_is_not_nullable():
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("device_routes")
    }
    assert columns["dev_eui"]["nullable"] is False
    assert columns["app_id"]["nullable"] is False
    assert columns["agent_endpoint"]["nullable"] is True


def test_device_routes_dev_eui_has_unique_index():
    indexes = [
        index
        for index in inspect(engine).get_indexes("device_routes")
        if index["column_names"] == ["dev_eui"]
    ]
    assert len(indexes) == 1
    assert indexes[0]["unique"] is True


def test_device_routes_app_id_foreign_key_targets_application():
    foreign_keys = [
        fk
        for fk in inspect(engine).get_foreign_keys("device_routes")
        if fk["constrained_columns"] == ["app_id"]
    ]
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_table"] == "application"
    assert foreign_keys[0]["referred_columns"] == ["id"]
```

- [ ] **Step 2: Rodar o teste**

Run: `cd saas_backend && poetry run pytest tests/test_device_routes_schema.py -q`
Expected: PASS (4 testes).

- [ ] **Step 3: Commit**

```bash
git add saas_backend/tests/test_device_routes_schema.py
git commit -m "test(backend): cobre o schema aplicado de device_routes"
```

---

## Task 6: Documentação

**Files:**
- Modify: `saas_backend/README.md`
- Modify: `PROGRESS.md`
- Modify: `SPRINTS_BACKLOG.md`

- [ ] **Step 1: README — checklist de models**

Em `saas_backend/README.md`, substituir:

```markdown
* [x] Models SQLAlchemy 2.0: `tenant`, `application`, `user`, `tenant_user`.
```

por:

```markdown
* [x] Models SQLAlchemy 2.0: `tenant`, `application`, `user`, `tenant_user`, `device_routes`.
```

- [ ] **Step 2: README — tabela de estrutura**

Substituir:

```markdown
| `src/linx/models/`               | Definição dos models (`tenant`, `application`, `user`, `tenant_user`). |
```

por:

```markdown
| `src/linx/models/`               | Definição dos models (`tenant`, `application`, `user`, `tenant_user`, `device_routes`). |
```

- [ ] **Step 3: README — tabela de Models**

Após a linha do model `TenantUser`, adicionar:

```markdown
| `DeviceRoute` | `device_routes` | Rota de telemetria: `dev_eui` único → `application.id` + `agent_endpoint` (nullable). |
```

- [ ] **Step 4: README — relacionamentos e verificação**

Substituir:

```markdown
- Relacionamentos ORM: `Tenant.applications` ↔ `Application.tenant` e `Tenant.tenant_users` ↔ `TenantUser` ↔ `User.tenant_users`.
```

por:

```markdown
- Relacionamentos ORM: `Tenant.applications` ↔ `Application.tenant`, `Tenant.tenant_users` ↔ `TenantUser` ↔ `User.tenant_users` e `Application.device_routes` ↔ `DeviceRoute.application`.
```

Substituir a saída esperada:

```text
dict_keys(['application', 'tenant', 'tenant_user', 'user'])
```

por:

```text
dict_keys(['application', 'device_routes', 'tenant', 'tenant_user', 'user'])
```

- [ ] **Step 5: PROGRESS.md**

Substituir a linha da issue #33:

```markdown
- [ ] [#33 feat(backend): device_routes table (dev_eui, app_id, agent_endpoint)](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/33)
```

por:

```markdown
- [x] [#33 feat(backend): device_routes table (dev_eui, app_id, agent_endpoint)](https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/33)
```

- [ ] **Step 6: SPRINTS_BACKLOG.md**

Substituir:

```markdown
- [ ] Tabela `device_routes` (`dev_eui`, `app_id`, `agent_endpoint`) para roteamento futuro.
```

por:

```markdown
- [x] Tabela `device_routes` (`dev_eui`, `app_id`, `agent_endpoint`) para roteamento futuro.
```

- [ ] **Step 7: Commit**

```bash
git add saas_backend/README.md PROGRESS.md SPRINTS_BACKLOG.md
git commit -m "docs(backend): documenta a tabela device_routes"
```

---

## Task 7: Verificação final (lint + typecheck + testes)

- [ ] **Step 1: Lint e typecheck**

Run: `cd saas_backend && poetry run black --check --diff . && poetry run isort --check --diff . && poetry run mypy src/ tests/ && poetry run flake8 src/ tests/`
Expected: sem erros.

- [ ] **Step 2: Suíte completa com cobertura**

Run: `cd saas_backend && poetry run pytest -q`
Expected: PASS.

- [ ] **Step 3: Confirmar git limpo (fora do escopo pré-existente)**

Run: `git status --short`
Expected: apenas o move pré-existente de `docs/plano_issues_github.md` (deletado + untracked em `docs/superpowers/plans/`), que **não** será commitado.

---

## Task 8: Code review interno e correções

- [ ] **Step 1: Invocar a skill `requesting-code-review`**

Revisar o diff dos 3 commits contra a spec, cobrindo: aderência ao snippet da issue (com a correção `application.id`), nullability, índices, registro do model, migration e testes.

- [ ] **Step 2: Corrigir achados**

Para cada achado válido, aplicar a correção, rodar `poetry run pytest -q` e criar um commit `fix(backend): ...` (não fazer amend de commit já feito).

- [ ] **Step 3: Repetir até não haver achados relevantes**

---

## Após o plano (aguardar autorização do usuário)

- **NÃO** fazer `git push` nem abrir PR sem autorização explícita.
- Quando autorizado: `git push -u origin issue33_devices_routes` e abrir PR referenciando a issue #33.

## Self-Review do plano

- **Cobertura da spec:** model (Task 2), relationship/registro (Task 2), migration (Task 3), testes de metadata (Task 1/4) e schema (Task 5), documentação (Task 6), validação (Task 7), code review (Task 8). ✓
- **Placeholders:** migration tem conteúdo esperado + instrução de revisão (autogerada); sem "TODO"/"implement later". ✓
- **Consistência de tipos:** `DeviceRoute`, `device_routes`, `application.id`, `Mapped[str | None]` usados de forma idêntica entre tasks. ✓
