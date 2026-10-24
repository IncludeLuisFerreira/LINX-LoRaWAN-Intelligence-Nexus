# Async Jobs Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o provisionamento síncrono por jobs assíncronos duráveis com RabbitMQ, outbox e worker genérico.

**Architecture:** O `identity_api` grava `jobs` e `job_outbox` na mesma transação e responde `202`. O `jobs_worker` publica o outbox, consome a fila do domínio, chama o `docker_provisioner` via gRPC e publica eventos de status. O `jobs_status_worker` aplica esses eventos na tabela `jobs`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Postgres, Alembic, RabbitMQ, pika, gRPC, pytest, poetry.

**Spec:** `docs/superpowers/specs/2026-10-24-async-jobs-platform-design.md`

## Global Constraints

- Caminhos de código são relativos a `linx_core/`. Caminhos em `docs/` são
  relativos à raiz do repositório (`Lynx/`). Comandos rodam de `linx_core/`
  salvo indicação contrária.
- Python `>=3.12,<4.0`.
- `black`, `isort`, `flake8` e `mypy` com line length 79.
- Código e nomes de API em inglês; documentação em português.
- Nunca commitar sem pedido explícito do usuário.
- Mensagens AMQP contêm apenas IDs e payload de domínio; nunca segredos.
- Semântica at-least-once; handlers e updates de status idempotentes.
- Ack RabbitMQ somente depois do commit no Postgres.
- Migration base: `a1b2c3d4e5f6`.
- Testes exigem Postgres em `localhost:5432`, como os testes atuais.
- Não alterar o contrato gRPC do `docker_provisioner`.

## Review Focus

- POST duplicado em corrida deve retornar o mesmo `job_id` e não criar dois jobs ativos.
- Worker que cai depois do claim e antes do ack deve permitir reentrega ou reclaim por lease.
- Evento `started`, `succeeded`, `failed` ou `retry` duplicado/atrasado não pode regredir job terminal.
- RabbitMQ indisponível no enqueue não pode impedir o `202`; o outbox publica depois.
- Erro transitório deve retryar; erro permanente deve falhar direto.
- `GET /jobs/{id}` não pode vazar job de outro tenant.
- Envelope e outbox não podem conter `SERVICE_TOKEN`, `DB_PASSWORD` ou credenciais.

---

### Task 1: Shared job domain, models and migration

**Files:**
- Create: `shared/src/linx_shared/jobs/__init__.py`
- Create: `shared/src/linx_shared/jobs/constants.py`
- Create: `shared/src/linx_shared/jobs/envelope.py`
- Create: `shared/src/linx_shared/models/job.py`
- Create: `shared/src/linx_shared/models/job_outbox.py`
- Modify: `shared/src/linx_shared/models/__init__.py`
- Modify: `shared/src/linx_shared/db/base.py`
- Create: `services/identity_api/migrations/versions/c3d4e5f6a7b8_add_jobs_tables.py`
- Test: `shared/tests/test_jobs.py`
- Modify: `shared/tests/test_models.py`

**Interfaces:**
- Produces: `linx_shared.jobs.constants.JobStatus`, `JOB_TYPE_PROVISION_APPLICATION`, `PROVISIONING_QUEUE`, `PROVISIONING_DLQ`, `PROVISIONING_STATUS_QUEUE`, `JOB_EXCHANGE`, `JOB_DLX`, `JOB_EVENTS_EXCHANGE`, `PROVISIONING_REQUESTED`, `PROVISIONING_STARTED`, `PROVISIONING_SUCCEEDED`, `PROVISIONING_FAILED`, `PROVISIONING_RETRY`, `PROVISIONING_DEAD`, `RETRY_DELAYS_SECONDS`.
- Produces: `linx_shared.jobs.envelope.JobEnvelope`, `JobError`, `JobStatusEvent`.
- Produces: `linx_shared.models.job.Job`, `linx_shared.models.job_outbox.JobOutbox`.

- [ ] **Step 1: Write the failing tests**

Create `shared/tests/test_jobs.py`:

```python
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    RETRY_DELAYS_SECONDS,
    JobStatus,
)
from linx_shared.jobs.envelope import JobEnvelope, JobStatusEvent
from linx_shared.models.job import Job
from linx_shared.models.job_outbox import JobOutbox


def test_retry_delays():
    assert RETRY_DELAYS_SECONDS == (5, 30, 120)


def test_job_defaults_and_columns():
    job = Job(
        type=JOB_TYPE_PROVISION_APPLICATION,
        tenant_id=uuid4(),
        subject_id=uuid4(),
        payload={"application_id": "x"},
        command_exchange="linx.jobs",
        command_routing_key="provisioning.application.requested",
        deduplication_key="provisioning.application:x",
    )
    assert job.status == JobStatus.PENDING.value
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.result is None
    assert job.error is None
    assert job.command_routing_key == "provisioning.application.requested"


def test_job_outbox_defaults():
    outbox = JobOutbox(
        job_id=uuid4(),
        exchange="linx.jobs",
        routing_key="provisioning.application.requested",
        payload={"job_id": "x"},
    )
    assert outbox.published_at is None
    assert outbox.attempts == 0


def test_job_envelope_round_trip():
    raw = {
        "job_id": str(uuid4()),
        "type": JOB_TYPE_PROVISION_APPLICATION,
        "tenant_id": str(uuid4()),
        "subject_id": str(uuid4()),
        "payload": {"application_id": "x"},
        "attempt": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    envelope = JobEnvelope.model_validate(raw)
    assert envelope.model_dump(mode="json")["type"] == (
        JOB_TYPE_PROVISION_APPLICATION
    )


def test_job_envelope_rejects_missing_tenant():
    with pytest.raises(ValidationError):
        JobEnvelope.model_validate(
            {
                "job_id": str(uuid4()),
                "type": JOB_TYPE_PROVISION_APPLICATION,
                "subject_id": str(uuid4()),
                "payload": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )


def test_status_event_supports_retry():
    event = JobStatusEvent(
        job_id=uuid4(),
        type=JOB_TYPE_PROVISION_APPLICATION,
        status=JobStatus.PENDING,
        attempt=1,
        next_attempt_at=datetime.now(timezone.utc),
    )
    assert event.status == JobStatus.PENDING
    assert event.next_attempt_at is not None
```

Update `shared/tests/test_models.py`:

- Expected table set includes `"jobs"` and `"job_outbox"`.
- Add assertions for `Job` UUID primary key, `deduplication_key` partial unique index, and `JobOutbox.job_id` FK with `ondelete == "CASCADE"`.
- Update the subprocess expected table list to include both new tables.

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_jobs.py tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'linx_shared.jobs'`.

- [ ] **Step 3: Implement constants and envelope**

`shared/src/linx_shared/jobs/constants.py` must define:

```python
class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

JOB_TYPE_PROVISION_APPLICATION = "provisioning.application"
JOB_EXCHANGE = "linx.jobs"
JOB_DLX = "linx.jobs.dlx"
JOB_EVENTS_EXCHANGE = "linx.jobs.events"
PROVISIONING_QUEUE = "linx.jobs.provisioning"
PROVISIONING_DLQ = "linx.jobs.provisioning.dlq"
PROVISIONING_STATUS_QUEUE = "linx.jobs.status"
PROVISIONING_REQUESTED = "provisioning.application.requested"
PROVISIONING_STARTED = "provisioning.application.started"
PROVISIONING_SUCCEEDED = "provisioning.application.succeeded"
PROVISIONING_FAILED = "provisioning.application.failed"
PROVISIONING_RETRY = "provisioning.application.retry"
PROVISIONING_DEAD = "provisioning.application.dead"
RETRY_DELAYS_SECONDS = (5, 30, 120)
```

Retry is scheduled by `job_outbox.next_attempt_at`, not by retry queues.

`shared/src/linx_shared/jobs/envelope.py` must define Pydantic models with
these fields and types:

```python
class JobError(BaseModel):
    code: str
    message: str
    retryable: bool
    grpc_code: str | None = None

class JobEnvelope(BaseModel):
    job_id: UUID
    type: str
    version: int = 1
    tenant_id: UUID
    subject_id: UUID
    payload: dict[str, Any]
    attempt: int = 0
    created_at: datetime
    trace_id: UUID | None = None

class JobStatusEvent(BaseModel):
    job_id: UUID
    type: str
    status: JobStatus
    attempt: int
    result: dict[str, Any] | None = None
    error: JobError | None = None
    next_attempt_at: datetime | None = None
    finished_at: datetime | None = None
```

- [ ] **Step 4: Implement SQLAlchemy models**

`shared/src/linx_shared/models/job.py` and `job_outbox.py` implement the
schema from the spec, including `command_exchange` and `command_routing_key`
on `jobs`. Use `UUID(as_uuid=True)`, `JSONB`, `DateTime(timezone=True)`,
`Mapped`, `mapped_column` and timezone-aware UTC defaults.

`Job.__table_args__` must include:

```python
Index(
    "uq_jobs_active_dedup",
    "deduplication_key",
    unique=True,
    postgresql_where=text("status IN ('pending','running')"),
)
Index("ix_jobs_status_next_attempt", "status", "next_attempt_at")
Index("ix_jobs_tenant_created", "tenant_id", text("created_at DESC"))
Index("ix_jobs_subject", "subject_id")
CheckConstraint(
    "status IN ('pending','running','succeeded','failed')",
    name="ck_jobs_status",
)
```

`JobOutbox` must include `exchange: Mapped[str]` (TEXT NOT NULL) in addition
to `routing_key`, `payload` and the other columns from the spec.

`JobOutbox.__table_args__` must include a partial index
`ix_job_outbox_pending` on `(published_at, next_attempt_at)` where
`published_at IS NULL`.

Update `models/__init__.py` and `db/base.py` so both models are imported and
registered.

- [ ] **Step 5: Create the migration**

Create `services/identity_api/migrations/versions/c3d4e5f6a7b8_add_jobs_tables.py`
with `revision = "c3d4e5f6a7b8"` and
`down_revision = "a1b2c3d4e5f6"`.

`upgrade()` creates `jobs` (including `command_exchange` and
`command_routing_key`), `job_outbox` (including the `exchange` column), the
check constraint and all indexes from the spec. `downgrade()` drops
`job_outbox`, then `jobs`.

- [ ] **Step 6: Run the tests**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_jobs.py tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Run migration against local Postgres**

```bash
env -u VIRTUAL_ENV poetry -C services/identity_api run alembic -c ../../alembic.ini upgrade head
```

Expected: migration `c3d4e5f6a7b8` applied.

- [ ] **Step 8: Run lint**

```bash
env -u VIRTUAL_ENV poetry -C shared run task lint
```

Expected: PASS.

---

### Task 2: Move Docker provisioner client to shared and expose gRPC code

**Files:**
- Create: `shared/src/linx_shared/clients/__init__.py`
- Create: `shared/src/linx_shared/clients/docker_provisioner.py`
- Create: `shared/tests/test_docker_provisioner_client.py`
- Delete: `services/identity_api/tests/test_provisioner_client.py`
- Modify: `services/identity_api/src/identity_api/provisioner_client.py`

**Interfaces:**
- Produces: `linx_shared.clients.docker_provisioner.DockerProvisionerClient`, `ProvisionedApplication`, `ProvisionerClientError`.
- `ProvisionerClientError(message: str, *, status_code: int = 502, grpc_code: grpc.StatusCode | None = None)`.
- `DockerProvisionerClient(*, target: str, service_token: str, timeout: float)`.
- `DockerProvisionerClient.provision(app_id: str) -> ProvisionedApplication`.

- [ ] **Step 1: Move the existing tests**

Copy `services/identity_api/tests/test_provisioner_client.py` to
`shared/tests/test_docker_provisioner_client.py`. Change imports to:

```python
from linx_shared.clients.docker_provisioner import (
    DockerProvisionerClient,
    ProvisionerClientError,
)
```

Add assertions that every mapped gRPC error preserves `exc_info.value.grpc_code`.

- [ ] **Step 2: Run the moved test to verify it fails**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_docker_provisioner_client.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the shared client**

Move the implementation from
`services/identity_api/src/identity_api/provisioner_client.py` to
`shared/src/linx_shared/clients/docker_provisioner.py`.

Keep the existing `_GRPC_TO_HTTP_STATUS` mapping and `ProvisionedApplication`
dataclass. Add `grpc_code` to `ProvisionerClientError` and set it in the
`except grpc.RpcError` block.

- [ ] **Step 4: Keep identity_api imports working temporarily**

The shared client constructor takes explicit values:

```python
DockerProvisionerClient(
    *,
    target: str,
    service_token: str,
    timeout: float,
)
```

Replace `services/identity_api/src/identity_api/provisioner_client.py` with a
temporary adapter that preserves the old zero-argument constructor:

```python
from linx_shared.clients.docker_provisioner import (
    DockerProvisionerClient as SharedDockerProvisionerClient,
    ProvisionedApplication,
    ProvisionerClientError,
)

from identity_api.config import settings


class DockerProvisionerClient(SharedDockerProvisionerClient):
    def __init__(
        self,
        *,
        target: str | None = None,
        service_token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            target=target or settings.provisioner_grpc_host,
            service_token=(
                settings.service_token
                if service_token is None
                else service_token
            ),
            timeout=(
                settings.provisioner_grpc_timeout_seconds
                if timeout is None
                else timeout
            ),
        )


__all__ = [
    "DockerProvisionerClient",
    "ProvisionedApplication",
    "ProvisionerClientError",
]
```

- [ ] **Step 5: Run shared and identity tests**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_docker_provisioner_client.py -v
env -u VIRTUAL_ENV poetry -C services/identity_api run pytest tests/test_application_provision.py -v
```

Expected: shared PASS; identity still PASS, because the re-export preserves the
old import path.

- [ ] **Step 6: Run lint**

```bash
env -u VIRTUAL_ENV poetry -C shared run task lint
```

Expected: PASS.

---

### Task 3: Job repository, RabbitMQ topology and outbox relay

**Files:**
- Create: `shared/src/linx_shared/jobs/repository.py`
- Create: `shared/src/linx_shared/jobs/broker.py`
- Create: `shared/src/linx_shared/jobs/outbox.py`
- Modify: `shared/pyproject.toml`
- Modify: `shared/poetry.lock`
- Create: `shared/tests/test_job_broker.py`
- Create: `shared/tests/test_job_repository.py`

**Interfaces:**
- Produces: `get_active_job(session, deduplication_key) -> Job | None`.
- Produces: `get_job(session, tenant_id, job_id) -> Job | None`.
- Produces: `create_job_with_outbox(session, *, job_type, tenant_id, subject_id, payload, deduplication_key, exchange, routing_key, max_attempts=3, trace_id=None) -> Job`.
- Produces: `claim_job(session, job_id, *, lock_seconds) -> Job | None`.
- Produces: `release_job(session, job_id, *, next_attempt_at=None) -> Job | None`.
- Produces: `apply_status_event(session, event) -> Job | None`.
- Produces: `JobPublisher` protocol, `RabbitMQPublisher(url)`, `declare_topology(channel)`.
- Produces: `relay_pending_outbox(session, publisher, *, now=None, batch_size=50) -> int`.

- [ ] **Step 1: Write repository tests**

Add a transaction-scoped Postgres fixture to `shared/tests/conftest.py`
(same pattern as `services/identity_api/tests/test_application_provision.py`)
and expose it as `db_session`.

`shared/tests/test_job_repository.py` uses that fixture.

Tests:

- `test_create_job_with_outbox_creates_both_rows` and stores the command
  exchange/routing key
- `test_get_active_job_ignores_terminal_jobs`
- `test_create_job_with_outbox_respects_active_dedup_index`
- `test_claim_job_sets_lease_and_attempt`
- `test_claim_job_ignores_valid_lease`
- `test_claim_job_ignores_future_next_attempt`
- `test_claim_job_reclaims_expired_lease`
- `test_release_job_clears_lease`
- `test_apply_status_event_is_idempotent`
- `test_apply_status_event_ignores_stale_attempt`
- `test_get_job_is_tenant_scoped`

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_job_repository.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the repository**

Use SQLAlchemy 2 style:

```python
def create_job_with_outbox(session, *, job_type, tenant_id, subject_id,
                           payload, deduplication_key, exchange, routing_key,
                           max_attempts=3, trace_id=None) -> Job:
    job = Job(
        type=job_type,
        tenant_id=tenant_id,
        subject_id=subject_id,
        payload=payload,
        command_exchange=exchange,
        command_routing_key=routing_key,
        deduplication_key=deduplication_key,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.flush()
    session.add(
        JobOutbox(
            job_id=job.id,
            exchange=exchange,
            routing_key=routing_key,
            payload=_envelope_payload(job, trace_id),
        )
    )
    return job
```

`_envelope_payload` builds the `JobEnvelope` from the job and serializes with
`model_dump(mode="json")`.

`claim_job` selects with `.with_for_update()`, returns `None` for terminal jobs,
a valid `locked_until`, or a future `next_attempt_at`. Otherwise increments
`attempts`, sets `started_at` on first attempt and
`locked_until = now + lock_seconds`. It does not change `status`; the
`started` event does that in the status worker.

`release_job` selects with `.with_for_update()`, clears `locked_until` and
optionally sets `next_attempt_at`. It does not change `status`.

`apply_status_event` selects with `.with_for_update()` and:

- ignores any event whose `attempt` is older than `job.attempts`;
- never moves a terminal job to a non-terminal status;
- applies events with `event.attempt == job.attempts` idempotently;
- on `running`, ignores the event if `job.next_attempt_at` is in the future;
  otherwise sets `started_at` if it is null;
- sets `result`, `error`, `status`, `finished_at`, `next_attempt_at` and clears
  `locked_until` as appropriate.

- [ ] **Step 4: Write broker tests**

`shared/tests/test_job_broker.py` uses a fake channel recording
`exchange_declare`, `queue_declare`, `queue_bind` and `basic_publish`.

Tests:

- `test_declare_topology_declares_exchanges_queues_and_bindings`
- `test_declare_topology_configures_main_queue_dlx`
- `test_publish_sets_persistent_message_and_message_id`

The outbox relay itself is covered by `services/jobs_worker/tests/test_outbox_relay.py`
against Postgres.

- [ ] **Step 5: Implement broker and outbox**

Add `pika` to `shared/pyproject.toml` and regenerate the lock:

```bash
env -u VIRTUAL_ENV poetry -C shared add pika
env -u VIRTUAL_ENV poetry -C services/identity_api lock
env -u VIRTUAL_ENV poetry -C services/agent_bridge lock
env -u VIRTUAL_ENV poetry -C services/docker_provisioner lock
```

`services/jobs_worker` is created in Task 5; generate its lock there.

Add a mypy override for `pika` in `shared/pyproject.toml` and in
`services/jobs_worker/pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["pika", "pika.*"]
ignore_missing_imports = true
```

`declare_topology(channel)` implements the topology from the spec with durable
exchanges and queues.

`RabbitMQPublisher.publish(exchange, routing_key, payload, *, message_id=None)`
uses `pika.BasicProperties(delivery_mode=2, content_type="application/json",
message_id=message_id)` and JSON-encoded body. It reconnects once on
`pika.exceptions.AMQPConnectionError`; if the second publish fails, the relay
schedules an outbox retry.

`relay_pending_outbox` selects pending rows with
`.with_for_update(skip_locked=True)`, publishes to `row.exchange` with
`row.routing_key` and `message_id=str(row.job_id)`, marks `published_at`, and
on failure increments `attempts` and sets `next_attempt_at`.

- [ ] **Step 6: Run tests and lint**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_job_repository.py tests/test_job_broker.py -v
env -u VIRTUAL_ENV poetry -C shared run task lint
```

Expected: PASS.

---

### Task 4: Async provisioning endpoint and job status endpoint

**Files:**
- Create: `services/identity_api/src/identity_api/jobs.py`
- Create: `services/identity_api/src/identity_api/routes/jobs.py`
- Modify: `services/identity_api/src/identity_api/routes/application.py:191-265`
- Modify: `services/identity_api/src/identity_api/schemas.py`
- Modify: `services/identity_api/src/identity_api/main.py`
- Modify: `services/identity_api/src/identity_api/dependencies.py`
- Modify: `services/identity_api/src/identity_api/config.py`
- Modify: `services/identity_api/tests/conftest.py`
- Delete: `services/identity_api/src/identity_api/provisioner_client.py`
- Delete: `services/identity_api/tests/test_provisioner_client.py`
- Test: `services/identity_api/tests/test_application_provision.py`
- Test: `services/identity_api/tests/test_jobs_route.py`
- Modify: `services/identity_api/tests/test_auth_all_routers.py`
- Modify: `services/identity_api/tests/test_openapi.py`
- Modify: `docs/openapi-stub.json`

**Interfaces:**
- Produces: `identity_api.jobs.create_provisioning_job(db: Session, tenant_id: UUID, application_id: UUID) -> Job`.
- Produces: `identity_api.jobs.get_tenant_job(db: Session, tenant_id: UUID, job_id: UUID) -> Job | None`.
- Produces: `JobAcceptedResponse`, `JobStatusResponse`, `JobErrorResponse`.
- Consumes: `linx_shared.models.job.Job`, `linx_shared.models.job_outbox.JobOutbox`.

- [ ] **Step 1: Write the failing API tests**

Rewrite `tests/test_application_provision.py` around the async contract:

```python
def test_provision_returns_202_with_pending_job():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    response = client.post(_provision_url(tenant_id, app_id))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["application_id"] == app_id
    assert response.headers["Location"].endswith(
        f"/api/v1/tenant/{tenant_id}/jobs/{body['job_id']}"
    )


def test_duplicate_provision_returns_same_job():
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    first = client.post(_provision_url(tenant_id, app_id))
    second = client.post(_provision_url(tenant_id, app_id))

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_provision_creates_one_outbox_row(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    client.post(_provision_url(tenant_id, app_id))

    rows = db_session.query(JobOutbox).all()
    assert len(rows) == 1
    assert rows[0].exchange == "linx.jobs"
    assert rows[0].routing_key == "provisioning.application.requested"
    assert rows[0].payload["type"] == "provisioning.application"


def test_provision_outbox_has_no_secrets(db_session):
    tenant_id = _create_tenant()
    app_id = _create_application(tenant_id)

    client.post(_provision_url(tenant_id, app_id))

    payload = db_session.query(JobOutbox).one().payload
    serialized = str(payload).lower()
    assert "service_token" not in serialized
    assert "db_password" not in serialized
    assert "password" not in serialized
```

Keep the existing 401, 404 tenant, 404 application and cross-tenant tests.
Replace the old 409/502/503/504 provisioner error tests with status endpoint
tests.

Add a `db_session` fixture to `services/identity_api/tests/conftest.py` that
yields the same transaction-scoped `Session` used by the existing
`override_get_db` fixture, so tests can query `Job` and `JobOutbox` directly.

Create `tests/test_jobs_route.py`:

```python
def test_get_job_returns_result(db_session):
    job = _seed_job(db_session, status="succeeded", result={"port": 8421})

    response = client.get(
        f"/api/v1/tenant/{job.tenant_id}/jobs/{job.id}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["result"] == {"port": 8421}


def test_get_job_from_other_tenant_returns_404(db_session):
    job = _seed_job(db_session, status="pending")

    response = client.get(
        f"/api/v1/tenant/{uuid4()}/jobs/{job.id}"
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
env -u VIRTUAL_ENV poetry -C services/identity_api run pytest tests/test_application_provision.py tests/test_jobs_route.py -v
```

Expected: FAIL; POST still returns `201` and jobs route is `404`.

- [ ] **Step 3: Implement `identity_api.jobs`**

`create_provisioning_job` must:

1. Build `deduplication_key = f"provisioning.application:{application_id}"`.
2. Return the active job if `get_active_job(db, key)` finds one.
3. Call `create_job_with_outbox(...)` from Task 3 with
   `job_type=JOB_TYPE_PROVISION_APPLICATION`,
   `subject_id=application_id`,
   `payload={"application_id": str(application_id)}`,
   `exchange=JOB_EXCHANGE`,
   `routing_key=PROVISIONING_REQUESTED`.
4. Commit the session.
5. On `IntegrityError`, rollback, re-query the active job, and return it. If
   no active job exists, re-raise the original error.

`get_tenant_job` must filter by both `tenant_id` and `job_id`.

- [ ] **Step 4: Implement the routes and schemas**

In `routes/application.py`, replace the body of `provision_application` with:

- validate tenant and application as today;
- `job = create_provisioning_job(db, tenant_id, application_id)`;
- set `response.headers["Location"] = f"/api/v1/tenant/{tenant_id}/jobs/{job.id}"`;
- return `JobAcceptedResponse(...)`.

The route decorator becomes:

```python
@router.post(
    "/{tenant_id}/applications/{application_id}/provision",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobAcceptedResponse,
)
```

Create `routes/jobs.py` with
`GET /api/v1/tenant/{tenant_id}/jobs/{job_id}` returning `JobStatusResponse`.

Add to `schemas.py`:

```python
class JobAcceptedResponse(BaseModel):
    job_id: UUID
    application_id: UUID
    status: JobStatus
    created_at: datetime

class JobErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    grpc_code: str | None = None

class JobStatusResponse(BaseModel):
    job_id: UUID
    type: str
    tenant_id: UUID
    subject_id: UUID
    status: JobStatus
    attempts: int
    max_attempts: int
    result: dict | None
    error: JobErrorResponse | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
```

- [ ] **Step 5: Remove the synchronous provisioner client from identity_api**

- Delete `identity_api/provisioner_client.py`.
- Remove `get_provisioner_client` and `close_provisioner_client` from
  `dependencies.py`.
- Remove `close_provisioner_client()` from the lifespan in `main.py`.
- Remove `provisioner_grpc_host` and `provisioner_grpc_timeout_seconds` from
  `config.py`.
- Include the new jobs router in `main.py`.
- Delete `tests/test_provisioner_client.py`.

- [ ] **Step 6: Update auth coverage and run API tests**

Add to the parameterized route list in
`services/identity_api/tests/test_auth_all_routers.py`:

```python
("post", "/api/v1/tenant/{tenant_id}/applications/{app_id}/provision"),
("get", "/api/v1/tenant/{tenant_id}/jobs/{job_id}"),
```

Extend the `.format(...)` call with `job_id=uuid4()`.

```bash
env -u VIRTUAL_ENV poetry -C services/identity_api run pytest tests/test_application_provision.py tests/test_jobs_route.py tests/test_auth_all_routers.py -v
```

Expected: PASS.

- [ ] **Step 7: Update OpenAPI tests and stub**

Add to `tests/test_openapi.py`:

```python
def test_openapi_exposes_job_status_endpoint():
    paths = _openapi()["paths"]
    assert "get" in paths["/api/v1/tenant/{tenant_id}/jobs/{job_id}"]
```

Regenerate `docs/openapi-stub.json`:

```bash
env -u VIRTUAL_ENV poetry -C services/identity_api run python - <<'PY'
import json
from pathlib import Path
from identity_api.main import app

Path("../../../docs/openapi-stub.json").write_text(
    json.dumps(app.openapi(), indent=2) + "\n"
)
PY
```

Run:

```bash
env -u VIRTUAL_ENV poetry -C services/identity_api run pytest tests/test_openapi.py -v
```

Expected: PASS.

---

### Task 5: Generic jobs worker and provisioning handler

**Files:**
- Create: `services/jobs_worker/pyproject.toml`
- Create: `services/jobs_worker/Dockerfile`
- Create: `services/jobs_worker/src/jobs_worker/__init__.py`
- Create: `services/jobs_worker/src/jobs_worker/config.py`
- Create: `services/jobs_worker/src/jobs_worker/main.py`
- Create: `services/jobs_worker/src/jobs_worker/runtime.py`
- Create: `services/jobs_worker/src/jobs_worker/processor.py`
- Create: `services/jobs_worker/src/jobs_worker/status.py`
- Create: `services/jobs_worker/src/jobs_worker/reaper.py`
- Create: `services/jobs_worker/src/jobs_worker/health.py`
- Create: `services/jobs_worker/src/jobs_worker/handlers/__init__.py`
- Create: `services/jobs_worker/src/jobs_worker/handlers/provision_application.py`
- Create: `shared/src/linx_shared/jobs/handlers.py`
- `services/jobs_worker/pyproject.toml` depends on `linx-shared`, `pika`,
  `pydantic-settings` and `grpcio`, with the same dev tools as the other
  services (`pytest`, `black`, `isort`, `flake8`, `mypy`, `pytest-cov`,
  `taskipy`). Generate `services/jobs_worker/poetry.lock` with
  `poetry -C services/jobs_worker lock`.
- Test: `services/jobs_worker/tests/conftest.py`
- Test: `services/jobs_worker/tests/test_provision_handler.py`
- Test: `services/jobs_worker/tests/test_job_processor.py`
- Test: `services/jobs_worker/tests/test_status_processor.py`
- Test: `services/jobs_worker/tests/test_outbox_relay.py`
- Test: `services/jobs_worker/tests/test_reaper.py`

**Interfaces:**
- Produces: `linx_shared.jobs.handlers.JobHandler`, `TransientJobError`, `PermanentJobError`, `HandlerRegistry`.
- Produces: `jobs_worker.handlers.provision_application.ProvisionApplicationHandler(client_factory: Callable[[], DockerProvisionerClient] | None = None)`.
- Produces: `jobs_worker.processor.JobProcessor(session_factory, registry, *, lock_seconds, retry_delays)` with `process(envelope)`. It writes outbox rows and never publishes directly.
- Produces: `jobs_worker.status.StatusProcessor(session_factory)` with `process(event)`.
- Produces: `jobs_worker.reaper.JobReaper(session_factory, *, interval_seconds=60)` with `run_once()` and `run_forever(stop_event)`.
- Produces: `jobs_worker.health.check() -> None`, which raises on DB or AMQP failure.
- Produces: `jobs_worker.runtime` consumer loops and `jobs_worker.main.main()`.

- [ ] **Step 1: Write handler tests**

`test_provision_handler.py`:

- success returns the expected result dict;
- `ProvisionerClientError(grpc_code=UNAVAILABLE)` raises `TransientJobError`;
- `ProvisionerClientError(grpc_code=FAILED_PRECONDITION)` raises
  `PermanentJobError`;
- payload application id is passed to the gRPC client.

- [ ] **Step 2: Write processor and status tests**

`services/jobs_worker/tests/conftest.py` sets `DATABASE_URL`,
`RABBITMQ_AMQP_URL`, `SERVICE_TOKEN` and `PROVISIONER_GRPC_HOST` before
importing the worker, and provides a transaction-scoped `session_factory` whose
sessions use `join_transaction_mode="create_savepoint"` on the same connection,
plus a `db_session` for assertions. Commits inside `JobProcessor` therefore do
not escape the outer test transaction.

`test_job_processor.py` uses that fixture. It asserts on `JobOutbox` rows
instead of a publisher.

Tests:

- success creates `started` and `succeeded` outbox rows and clears
  `locked_until`; job status remains unchanged until `StatusProcessor` runs;
- transient failure creates a `retry` event and a delayed command outbox row
  using the job's command exchange/routing key, sets `next_attempt_at`, and
  clears `locked_until`;
- permanent failure creates `failed` and DLQ outbox rows and clears
  `locked_until`;
- max attempts creates `failed` and DLQ outbox rows;
- duplicate message for a valid `locked_until` returns without new outbox
  rows;
- unexpected exception becomes `handler_error` retry;
- unknown `type` becomes a permanent failure;
- commit failure leaves no uncommitted outbox row.

`test_reaper.py`:

- expired lease creates a retry outbox row and clears `locked_until`; job
  status remains unchanged until `StatusProcessor` applies `pending`;
- valid lease is left untouched;
- reaper is idempotent when run twice.

`test_status_processor.py`:

- `started` moves `pending` to `running`;
- `succeeded` stores result;
- duplicate `succeeded` is ignored;
- late `started` after `succeeded` does not regress;
- older attempt event is ignored.

`test_outbox_relay.py`:

- pending row is published and marked;
- publisher failure increments attempts and schedules retry;
- two relay instances do not publish the same row twice (use two sessions and
  `SKIP LOCKED`).

- [ ] **Step 3: Run tests to verify they fail**

```bash
env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest -v
```

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement handler primitives and worker settings**

`jobs_worker/config.py` subclasses `linx_shared.core.config.Settings` and
defines `rabbitmq_amqp_url`, `worker_queue`, `worker_concurrency`,
`worker_prefetch`, `job_max_attempts`, `job_lock_seconds`,
`job_reaper_interval_seconds`, `provisioner_grpc_host` and
`provisioner_grpc_timeout_seconds`. Validate `rabbitmq_amqp_url` with
`require_connection_string("RABBITMQ_AMQP_URL", value, ("guest:guest",))` and
reject non-positive worker/timeout values.

`shared/src/linx_shared/jobs/handlers.py`:

```python
class TransientJobError(Exception):
    def __init__(self, message: str, *, code: str = "transient_error",
                 grpc_code: str | None = None) -> None: ...

class PermanentJobError(Exception):
    def __init__(self, message: str, *, code: str = "permanent_error",
                 grpc_code: str | None = None) -> None: ...

class JobHandler(Protocol):
    job_type: str
    def handle(self, job: Job) -> dict[str, Any]: ...

class HandlerRegistry:
    def register(self, handler: JobHandler) -> None: ...
    def get(self, job_type: str) -> JobHandler: ...
```

`get` raises `KeyError` for unknown types.

- [ ] **Step 5: Implement the provisioning handler**

`ProvisionApplicationHandler` reads `job.subject_id`, calls
`DockerProvisionerClient(target=settings.provisioner_grpc_host,
service_token=settings.service_token,
timeout=settings.provisioner_grpc_timeout_seconds).provision(str(job.subject_id))`,
closes the client in `finally`, and returns:

```python
{
    "container_id": result.container_id,
    "port": result.port,
    "network": result.network,
    "image": result.image,
    "status": result.status,
    "created": result.created,
    "mqtt_topic": result.mqtt_topic,
}
```

Map `ProvisionerClientError` by `grpc_code` using the spec classification.

- [ ] **Step 6: Implement processors**

Routing keys de status são derivados do tipo:
`f"{job.type}.started"`, `.succeeded`, `.failed`, `.retry` e `.dead`.

`JobProcessor.process(envelope)`:

1. Claim job with `claim_job`.
2. If no claim, return.
3. Add a `JobOutbox` row for `started` on `JOB_EVENTS_EXCHANGE` and commit.
4. Resolve handler.
5. Execute handler.
6. On success, add a `succeeded` outbox row and clear `locked_until`; commit.
7. On transient error, add a `retry` event outbox row and a delayed command
   outbox row using `job.command_exchange`/`job.command_routing_key` with
   `next_attempt_at = now + backoff`, set `next_attempt_at`, clear
   `locked_until`; commit. If attempts are exhausted, fail instead.
8. On permanent error, add a `failed` event outbox row and a DLQ message
   outbox row (`exchange=JOB_DLX`, routing key `PROVISIONING_DEAD`); clear
   `locked_until`; commit.
9. Never publish to RabbitMQ directly and never write terminal job status.
   The consumer acks after `process` returns.

`StatusProcessor.process(event)` calls `apply_status_event` and commits. It is
the only component that sets `running`, `pending`, `succeeded` and `failed`.

- [ ] **Step 7: Implement runtime and main**

`runtime.py` provides:

- `run_outbox_relay(stop_event, session_factory, publisher, poll_interval)`.
- `run_consumer(queue, callback, url, prefetch)` with manual ack and
  `basic_nack(requeue=True)` on processor exceptions.
- `build_registry()` registering `ProvisionApplicationHandler`.

`main.py` loads `WorkerSettings`, retries `health.check()` and a
`SELECT 1 FROM jobs LIMIT 1` for up to 30 attempts (2s apart) to tolerate the
migration running in `identity_api`, declares topology, starts the outbox relay
thread, the job reaper, the provisioning consumer and the status consumer, and
waits for SIGTERM/SIGINT. `JobProcessor` and `StatusProcessor` log one line per
message with `job_id`, `type`, `attempt`, `duration_ms` and `status`.

`JobReaper.run_once()` selects jobs with `locked_until < now()` and status in
`pending`/`running` using `.with_for_update(skip_locked=True)`, sets
`next_attempt_at = now()`, clears `locked_until`, inserts a retry event in
`job_outbox` on `JOB_EVENTS_EXCHANGE`, and inserts a retry message using the
job's `command_exchange` and `command_routing_key`.

- [ ] **Step 8: Run worker tests**

```bash
env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest -v
```

Expected: PASS.

- [ ] **Step 9: Run lint**

```bash
env -u VIRTUAL_ENV poetry -C services/jobs_worker run task lint
```

Expected: PASS.

---

### Task 6: Compose, environment, scripts and documentation

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `scripts/run.sh`
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `services/identity_api/tests/conftest.py`

**Interfaces:**
- Consumes: `jobs_worker` image and env from Task 5.
- Produces: `rabbitmq` service and `jobs_worker` service in Compose.

- [ ] **Step 1: Add RabbitMQ and worker to Compose**

Add:

```yaml
rabbitmq:
  image: rabbitmq:3-management-alpine
  restart: unless-stopped
  environment:
    - RABBITMQ_DEFAULT_USER=${RABBITMQ_ADMIN_USER:-linx}
    - RABBITMQ_DEFAULT_PASS=${RABBITMQ_ADMIN_PASSWORD:?RABBITMQ_ADMIN_PASSWORD must be set}
  ports:
    - "5672:5672"
    - "15672:15672"
  volumes:
    - rabbitmqdata:/var/lib/rabbitmq
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
```

Add `jobs_worker`:

```yaml
jobs_worker:
  build:
    context: .
    dockerfile: services/jobs_worker/Dockerfile
  restart: unless-stopped
  env_file: .env
  environment:
    - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-linx}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}@db:5432/${POSTGRES_DB:-linx}
    - RABBITMQ_AMQP_URL=amqp://${RABBITMQ_ADMIN_USER:-linx}:${RABBITMQ_ADMIN_PASSWORD:?RABBITMQ_ADMIN_PASSWORD must be set}@rabbitmq:5672/
    - SERVICE_TOKEN=${SERVICE_TOKEN:?SERVICE_TOKEN must be set}
    - PROVISIONER_GRPC_HOST=docker_provisioner:50052
    - PROVISIONER_GRPC_TIMEOUT_SECONDS=${PROVISIONER_GRPC_TIMEOUT_SECONDS:-10}
    - WORKER_QUEUE=linx.jobs.provisioning
    - WORKER_CONCURRENCY=${WORKER_CONCURRENCY:-4}
    - WORKER_PREFETCH=${WORKER_PREFETCH:-4}
    - JOB_MAX_ATTEMPTS=${JOB_MAX_ATTEMPTS:-3}
    - JOB_LOCK_SECONDS=${JOB_LOCK_SECONDS:-60}
    - JOB_REAPER_INTERVAL_SECONDS=${JOB_REAPER_INTERVAL_SECONDS:-60}
  depends_on:
    db:
      condition: service_healthy
    rabbitmq:
      condition: service_healthy
    docker_provisioner:
      condition: service_started
  healthcheck:
    test: ["CMD", "python", "-c", "from jobs_worker.health import check; check()"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 10s
```

Add `rabbitmqdata` to `volumes`.

Remove `PROVISIONER_GRPC_HOST` and `PROVISIONER_GRPC_TIMEOUT_SECONDS` from
`identity_api`; it no longer calls the provisioner.

- [ ] **Step 2: Update `.env.example`**

Add:

```text
RABBITMQ_AMQP_URL=amqp://linx:change-me-in-production@localhost:5672/
WORKER_QUEUE=linx.jobs.provisioning
WORKER_CONCURRENCY=4
WORKER_PREFETCH=4
JOB_MAX_ATTEMPTS=3
JOB_LOCK_SECONDS=60
JOB_REAPER_INTERVAL_SECONDS=60
```

Keep `PROVISIONER_GRPC_HOST` and `PROVISIONER_GRPC_TIMEOUT_SECONDS` for the
worker. Update comments to say they now belong to `jobs_worker`.

- [ ] **Step 3: Update local run script**

Add a `jobs_worker` process after `docker_provisioner`:

```bash
echo "Subindo jobs_worker (RabbitMQ)..."
poetry -C services/jobs_worker run python -m jobs_worker.main &
pids+=("$!")
```

Document that RabbitMQ must be running locally.

- [ ] **Step 4: Update root test task**

Add `services/jobs_worker` to `[tool.taskipy.tasks].test`:

```toml
test = "env -u VIRTUAL_ENV poetry -C shared run pytest && env -u VIRTUAL_ENV poetry -C services/identity_api run pytest && env -u VIRTUAL_ENV poetry -C services/agent_bridge run pytest && env -u VIRTUAL_ENV poetry -C services/docker_provisioner run pytest && env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest"
```

- [ ] **Step 5: Update README**

Update:

- architecture diagram with RabbitMQ and `jobs_worker`;
- endpoint table: `POST .../provision` returns `202` and
  `GET /api/v1/tenant/{id}/jobs/{job_id}`;
- async flow and state machine;
- env vars;
- local run instructions;
- note that messages contain no secrets and that the worker does not mount the
  Docker socket.

- [ ] **Step 6: Update test environment**

Add to `services/identity_api/tests/conftest.py`:

```python
os.environ.setdefault(
    "RABBITMQ_AMQP_URL",
    "amqp://linx:ci-rabbit-pass@localhost:5672/",
)
```

Add `services/jobs_worker/tests/conftest.py` with `DATABASE_URL`,
`RABBITMQ_AMQP_URL`, `SERVICE_TOKEN` and a Postgres transaction fixture.

- [ ] **Step 7: Validate Compose config**

```bash
docker compose config >/dev/null
```

Expected: exit code 0.

---

### Task 7: End-to-end verification

**Files:**
- No new files.

- [ ] **Step 1: Run the full test suite**

```bash
env -u VIRTUAL_ENV poetry -C shared run pytest
env -u VIRTUAL_ENV poetry -C services/identity_api run pytest
env -u VIRTUAL_ENV poetry -C services/docker_provisioner run pytest
env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest
```

Expected: all PASS.

- [ ] **Step 2: Run lint in every changed package**

```bash
env -u VIRTUAL_ENV poetry -C shared run task lint
env -u VIRTUAL_ENV poetry -C services/identity_api run task lint
env -u VIRTUAL_ENV poetry -C services/jobs_worker run task lint
```

Expected: all PASS.

- [ ] **Step 3: Apply migration on a clean database**

```bash
env -u VIRTUAL_ENV poetry -C services/identity_api run alembic -c ../../alembic.ini upgrade head
env -u VIRTUAL_ENV poetry -C services/identity_api run alembic -c ../../alembic.ini downgrade -1
env -u VIRTUAL_ENV poetry -C services/identity_api run alembic -c ../../alembic.ini upgrade head
```

Expected: upgrade, downgrade and upgrade complete without error.

- [ ] **Step 4: Manual smoke test**

With Compose running:

```bash
TOKEN="$(grep '^SERVICE_TOKEN=' .env | cut -d= -f2-)"
curl -X POST \
  "http://localhost:8000/api/v1/tenant/$TENANT_ID/applications/$APP_ID/provision" \
  -H "X-Service-Token: $TOKEN"
```

Expected: `202` with `job_id`.

```bash
curl \
  "http://localhost:8000/api/v1/tenant/$TENANT_ID/jobs/$JOB_ID" \
  -H "X-Service-Token: $TOKEN"
```

Expected: eventual `status=succeeded` and `result.container_id` populated.

- [ ] **Step 5: Confirm no secrets in messages**

```bash
docker compose exec rabbitmq rabbitmqctl list_queues name messages
```

Inspect a message only in a controlled environment and confirm it contains
`job_id`, `type`, `tenant_id`, `subject_id` and `payload` with IDs only. No
`SERVICE_TOKEN`, `DB_PASSWORD` or passwords.
