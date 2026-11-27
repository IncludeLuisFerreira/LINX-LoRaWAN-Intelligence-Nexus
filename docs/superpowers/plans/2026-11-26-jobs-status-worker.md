# Jobs Status Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extrair o consumo de eventos de status do `jobs_worker` para um serviço `jobs_status_worker` próprio, com imagem, deploy e CI independentes (#232).

**Architecture:** Um novo pacote Python `linx_core/services/jobs_status_worker/` consome apenas `linx.jobs.status` e aplica `JobStatusEvent` via `StatusProcessor`. O loop AMQP genérico migra para `linx_shared.jobs.consumer`; o `jobs_worker` deixa de consumir status e mantém apenas domínio, outbox relay e reaper.

**Tech Stack:** Python 3.12, Poetry 2.4.1, pika/RabbitMQ, SQLAlchemy/Postgres, Docker, Kubernetes/Kustomize, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-26-jobs-status-worker-design.md`

## Global Constraints

- Python `>=3.12,<4.0`; Poetry `2.4.1`.
- `black`/`isort` com `line-length = 79`; `flake8` e `mypy` sem erros.
- Cobertura de CI `>=70%` por pacote.
- Commits em português, Conventional Commits, sempre com `(#232)`.
- Branch de trabalho: `feat/jobs-status-worker` (já existe, limpa).
- `git add` explícito por arquivo; nunca `git add .`, `git add -A` ou `git commit -a`.
- Não alterar arquivos fora das listas de cada task; problemas fora de escopo devem ser reportados em vez de corrigidos.
- Nenhum segredo real em código, compose, manifestos ou documentação.
- Testes que exigem Postgres usam `DATABASE_URL`; os conftests definem defaults locais.

## Review Focus

Estes são os modos de falha que a spec implica e que os testes de cada task devem pinar:

1. **Evento de status malformado/venenoso** — deve ser `nack` sem requeue, para não criar loop infinito. Teste no consumidor compartilhado (Task 1).
2. **Evento duplicado ou atrasado** — não pode regredir job terminal nem sobrescrever `finished_at`. Teste no `StatusProcessor` (Task 3).
3. **Boot com Postgres/RabbitMQ indisponível** — deve tentar novamente com intervalo e falhar de forma explícita após o limite (container reinicia), nunca consumir antes de pronto. Teste em `_wait_for_dependencies` (Task 4).
4. **Configuração mínima** — o status worker deve subir só com `DATABASE_URL` + `RABBITMQ_AMQP_URL`, sem `SERVICE_TOKEN`/`PROVISIONER_GRPC_HOST`. Teste de settings (Task 2).
5. **Fila errada/omitida** — o default deve ser exatamente `linx.jobs.status`, e fila vazia deve ser rejeitada. Teste de settings (Task 2) e wiring do consumidor (Task 4).

---

### Task 1: Extrair o consumidor AMQP para `linx_shared`

**Files:**
- Create: `linx_core/shared/src/linx_shared/jobs/consumer.py`
- Create: `linx_core/shared/tests/test_job_consumer.py`
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/runtime.py`
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/main.py`
- Modify: `linx_core/services/jobs_worker/tests/test_runtime.py`

**Interfaces:**
- Consumes: `pika.BlockingConnection`, `pika.URLParameters`.
- Produces:
  - `linx_shared.jobs.consumer.InvalidMessageError(Exception)`
  - `linx_shared.jobs.consumer.RECONNECT_DELAY_SECONDS: float = 5.0`
  - `linx_shared.jobs.consumer.run_consumer(queue: str, callback: Callable[[bytes], None], url: str, prefetch: int, stop_event: threading.Event | None = None, *, declare: Callable[[Any], None] | None = None) -> None`

- [ ] **Step 1: Rodar o baseline dos testes**

```bash
cd linx_core
poetry -C shared run pytest -q
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://linx@127.0.0.1:5432/linx}" \
  poetry -C services/jobs_worker run pytest -q
```

Expected: PASS nos dois pacotes antes de qualquer mudança.

- [ ] **Step 2: Criar o teste compartilhado do consumidor**

Criar `linx_core/shared/tests/test_job_consumer.py` movendo os cinco testes de
consumidor de `linx_core/services/jobs_worker/tests/test_runtime.py:80-197`
(`test_run_consumer_*`, `test_invalid_message_is_nacked_without_requeue`,
`test_consumer_declares_topology_on_each_reconnect`) com:
- `from linx_shared.jobs import consumer` no lugar de `from jobs_worker import runtime`;
- `consumer.run_consumer(...)` e `consumer.InvalidMessageError`;
- `monkeypatch.setattr(consumer.pika, "BlockingConnection", factory)` no helper `_patch_connection`;
- `monkeypatch.setattr(consumer, "RECONNECT_DELAY_SECONDS", 0.0)` nos testes de reconexão.

- [ ] **Step 3: Rodar o teste novo para ver falhar**

```bash
cd linx_core
poetry -C shared run pytest tests/test_job_consumer.py -q
```

Expected: FAIL com `ModuleNotFoundError`/`ImportError` para `linx_shared.jobs.consumer`.

- [ ] **Step 4: Criar `consumer.py`**

Mover verbatim de `jobs_worker/runtime.py:23-141` (constante
`RECONNECT_DELAY_SECONDS`, `InvalidMessageError`, `_close_quietly`,
`run_consumer`), preservando a assinatura do bloco **Interfaces**. O arquivo
deve importar apenas `logging`, `threading`, `time`, `collections.abc.Callable`,
`typing.Any` e `pika`.

- [ ] **Step 5: Enxugar `jobs_worker/runtime.py`**

Remover `import pika`, `import time`, `RECONNECT_DELAY_SECONDS`,
`InvalidMessageError`, `_close_quietly` e `run_consumer`. Manter
`run_outbox_relay`, `_not_leader_or_not_ready` e `build_registry`. Remover
imports que ficarem sem uso.

- [ ] **Step 6: Atualizar imports do `jobs_worker/main.py`**

Trocar a importação de `run_consumer`/`InvalidMessageError` de
`jobs_worker.runtime` para:

```python
from linx_shared.jobs.consumer import InvalidMessageError, run_consumer
```

- [ ] **Step 7: Enxugar `test_runtime.py`**

Remover as classes `FakeMethod`, `FakeChannel`, `StoppingConnection`,
`FailingConnection`, `_patch_connection`, o import de `threading` e os testes
movidos. Manter os testes de `_parse_envelope`/`_parse_status_event`, importando
`InvalidMessageError` de `linx_shared.jobs.consumer`.

- [ ] **Step 8: Rodar testes e lint**

```bash
cd linx_core
poetry -C shared run pytest -q
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://linx@127.0.0.1:5432/linx}" \
  poetry -C services/jobs_worker run pytest -q
poetry -C shared run black --check src tests
poetry -C shared run isort --check-only src tests
poetry -C services/jobs_worker run black --check src tests
poetry -C services/jobs_worker run isort --check-only src tests
poetry -C services/jobs_worker run flake8 src tests
poetry -C services/jobs_worker run mypy src tests
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add linx_core/shared/src/linx_shared/jobs/consumer.py \
  linx_core/shared/tests/test_job_consumer.py \
  linx_core/services/jobs_worker/src/jobs_worker/runtime.py \
  linx_core/services/jobs_worker/src/jobs_worker/main.py \
  linx_core/services/jobs_worker/tests/test_runtime.py
git commit -m "refactor(shared): extrai consumidor AMQP para linx_shared (#232)"
```

---

### Task 2: Criar o pacote `jobs_status_worker` e o settings mínimo

**Files:**
- Create: `linx_core/services/jobs_status_worker/pyproject.toml`
- Create: `linx_core/services/jobs_status_worker/poetry.lock` (gerado)
- Create: `linx_core/services/jobs_status_worker/src/jobs_status_worker/__init__.py`
- Create: `linx_core/services/jobs_status_worker/src/jobs_status_worker/config.py`
- Create: `linx_core/services/jobs_status_worker/tests/conftest.py`
- Create: `linx_core/services/jobs_status_worker/tests/test_startup_config.py`

**Interfaces:**
- Consumes: `linx_shared.core.config.Settings`, `require_connection_string`; `linx_shared.jobs.constants.PROVISIONING_STATUS_QUEUE`.
- Produces:
  - `jobs_status_worker.config.StatusWorkerSettings(Settings)` com campos `rabbitmq_amqp_url: str`, `status_queue: str`, `status_concurrency: int`, `status_prefetch: int`.
  - `jobs_status_worker.config.settings: StatusWorkerSettings`.

- [ ] **Step 1: Criar `pyproject.toml`**

Modelar em `services/jobs_worker/pyproject.toml`, com estas diferenças:

```toml
[project]
name = "jobs-status-worker"
version = "0.1.0"
description = "Consumidor de eventos de status dos jobs assíncronos."

[tool.poetry]
packages = [{include = "jobs_status_worker", from = "src"}]

[tool.poetry.dependencies]
linx-shared = { path = "../../shared", develop = true }
pika = ">=1.4.4,<2.0.0"
pydantic-settings = ">=2.15.0,<3.0.0"
sqlalchemy = ">=2.0.52,<3.0.0"
psycopg = { version = ">=3.3.4,<4.0.0", extras = ["binary"] }

[tool.taskipy.tasks]
test = "pytest -s -x --cov=src -vv"
run = "poetry run python -m jobs_status_worker.main"
```

Não incluir `grpcio` nem dependência de `jobs_worker`. Copiar as seções
`[build-system]`, `[dependency-groups]`, `[tool.pytest.ini_options]`,
`[tool.black]`, `[tool.isort]` e os overrides de mypy para `pika` do
`jobs_worker`.

- [ ] **Step 2: Criar `conftest.py` mínimo**

```python
import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://linx@127.0.0.1:5432/linx",
)
os.environ.setdefault(
    "RABBITMQ_AMQP_URL",
    "amqp://linx:ci-rabbit-pass@localhost:5672/",
)
```

- [ ] **Step 3: Escrever os testes de configuração (falhando)**

`tests/test_startup_config.py`:

```python
import pytest
from linx_shared.jobs.constants import PROVISIONING_STATUS_QUEUE
from pydantic import ValidationError

from jobs_status_worker.config import StatusWorkerSettings


def _valid_env(monkeypatch):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL",
        "amqp://linx:real-rabbit-pass@localhost:5672/",
    )


def test_defaults(monkeypatch):
    _valid_env(monkeypatch)

    settings = StatusWorkerSettings(_env_file=None)

    assert settings.status_queue == PROVISIONING_STATUS_QUEUE
    assert settings.status_queue == "linx.jobs.status"
    assert settings.status_concurrency == 2
    assert settings.status_prefetch == 4


def test_does_not_require_service_token_or_provisioner_host(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.delenv("SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("PROVISIONER_GRPC_HOST", raising=False)

    settings = StatusWorkerSettings(_env_file=None)

    assert settings.service_token == ""


def test_rejects_missing_rabbitmq_url(monkeypatch):
    monkeypatch.delenv("RABBITMQ_AMQP_URL", raising=False)

    with pytest.raises(ValidationError, match="RABBITMQ_AMQP_URL"):
        StatusWorkerSettings(_env_file=None)


def test_rejects_guest_rabbitmq(monkeypatch):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL", "amqp://guest:guest@localhost:5672/"
    )

    with pytest.raises(ValidationError, match="guest:guest"):
        StatusWorkerSettings(_env_file=None)


def test_rejects_empty_status_queue(monkeypatch):
    _valid_env(monkeypatch)
    monkeypatch.setenv("STATUS_QUEUE", "  ")

    with pytest.raises(ValidationError, match="STATUS_QUEUE"):
        StatusWorkerSettings(_env_file=None)


@pytest.mark.parametrize("var", ["STATUS_CONCURRENCY", "STATUS_PREFETCH"])
@pytest.mark.parametrize("value", ["0", "-1"])
def test_rejects_non_positive_ints(monkeypatch, var, value):
    _valid_env(monkeypatch)
    monkeypatch.setenv(var, value)

    with pytest.raises(ValidationError, match="maior que zero"):
        StatusWorkerSettings(_env_file=None)
```

- [ ] **Step 4: Instalar dependências e rodar o teste para ver falhar**

```bash
cd linx_core
poetry -C services/jobs_status_worker install
poetry -C services/jobs_status_worker run pytest tests/test_startup_config.py -q
```

Expected: FAIL com `ModuleNotFoundError` para `jobs_status_worker.config`.

- [ ] **Step 5: Implementar `config.py`**

```python
from linx_shared.core.config import Settings, require_connection_string
from linx_shared.jobs.constants import PROVISIONING_STATUS_QUEUE
from pydantic import field_validator


class StatusWorkerSettings(Settings):
    rabbitmq_amqp_url: str = ""
    status_queue: str = PROVISIONING_STATUS_QUEUE
    status_concurrency: int = 2
    status_prefetch: int = 4

    @field_validator("rabbitmq_amqp_url")
    @classmethod
    def _validate_rabbitmq_amqp_url(cls, value: str) -> str:
        return require_connection_string(
            "RABBITMQ_AMQP_URL",
            value,
            ("guest:guest",),
        )

    @field_validator("status_queue")
    @classmethod
    def _validate_status_queue(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError(
                "STATUS_QUEUE is required and must not be empty."
            )
        return cleaned

    @field_validator("status_concurrency", "status_prefetch")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(f"{value!r} deve ser maior que zero")
        return value


settings = StatusWorkerSettings()
```

- [ ] **Step 6: Rodar testes, gerar lock e checar lint**

```bash
cd linx_core
poetry -C services/jobs_status_worker lock
poetry -C services/jobs_status_worker run pytest tests/test_startup_config.py -q
poetry -C services/jobs_status_worker run black --check src tests
poetry -C services/jobs_status_worker run isort --check-only src tests
poetry -C services/jobs_status_worker run flake8 src tests
poetry -C services/jobs_status_worker run mypy src tests
```

Expected: PASS. Se `mypy` reclamar do validador com `f"{value!r}"`, use uma
mensagem fixa `"valor deve ser maior que zero"`.

- [ ] **Step 7: Commit**

```bash
git add linx_core/services/jobs_status_worker/pyproject.toml \
  linx_core/services/jobs_status_worker/poetry.lock \
  linx_core/services/jobs_status_worker/src/jobs_status_worker/__init__.py \
  linx_core/services/jobs_status_worker/src/jobs_status_worker/config.py \
  linx_core/services/jobs_status_worker/tests/conftest.py \
  linx_core/services/jobs_status_worker/tests/test_startup_config.py
git commit -m "feat(jobs_status_worker): cria serviço e settings mínimo (#232)"
```

---

### Task 3: Mover o `StatusProcessor` para o novo serviço

**Files:**
- Create: `linx_core/services/jobs_status_worker/src/jobs_status_worker/status.py`
- Create: `linx_core/services/jobs_status_worker/tests/test_status_processor.py`
- Modify: `linx_core/services/jobs_status_worker/tests/conftest.py`

**Interfaces:**
- Consumes: `linx_shared.jobs.envelope.JobStatusEvent`, `linx_shared.jobs.repository.apply_status_event`, `sqlalchemy.orm.Session`.
- Produces: `jobs_status_worker.status.StatusProcessor(session_factory: Callable[[], Session])` com `process(event: JobStatusEvent) -> None`.

- [ ] **Step 1: Escrever o teste movido (falhando)**

Copiar `linx_core/services/jobs_worker/tests/test_status_processor.py` para
`linx_core/services/jobs_status_worker/tests/test_status_processor.py`,
trocando apenas o import para:

```python
from jobs_status_worker.status import StatusProcessor
```

- [ ] **Step 2: Adicionar as fixtures de banco ao `conftest.py`**

Copiar de `services/jobs_worker/tests/conftest.py` as fixtures `connection`,
`session_factory`, `db_session` e `job_factory`, junto com os imports
necessários (`pytest`, `Callable`, `Generator`, `datetime`, `Any`, `UUID`,
`uuid4`). Manter os `os.environ.setdefault` já criados na Task 2.

- [ ] **Step 3: Rodar o teste para ver falhar**

```bash
cd linx_core
poetry -C services/jobs_status_worker run pytest tests/test_status_processor.py -q
```

Expected: FAIL com `ModuleNotFoundError` para `jobs_status_worker.status`.

- [ ] **Step 4: Implementar `status.py`**

Mover verbatim `linx_core/services/jobs_worker/src/jobs_worker/status.py` para
o novo pacote, sem mudanças de comportamento.

- [ ] **Step 5: Rodar testes e lint**

```bash
cd linx_core
poetry -C services/jobs_status_worker run pytest tests/test_status_processor.py -q
poetry -C services/jobs_status_worker run black --check src tests
poetry -C services/jobs_status_worker run isort --check-only src tests
poetry -C services/jobs_status_worker run flake8 src tests
poetry -C services/jobs_status_worker run mypy src tests
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add linx_core/services/jobs_status_worker/src/jobs_status_worker/status.py \
  linx_core/services/jobs_status_worker/tests/test_status_processor.py \
  linx_core/services/jobs_status_worker/tests/conftest.py
git commit -m "feat(jobs_status_worker): move StatusProcessor para o serviço (#232)"
```

---

### Task 4: Healthcheck e entrypoint do consumidor de status

**Files:**
- Create: `linx_core/services/jobs_status_worker/src/jobs_status_worker/health.py`
- Create: `linx_core/services/jobs_status_worker/src/jobs_status_worker/main.py`
- Create: `linx_core/services/jobs_status_worker/tests/test_health.py`
- Create: `linx_core/services/jobs_status_worker/tests/test_main.py`

**Interfaces:**
- Consumes:
  - `jobs_status_worker.config.StatusWorkerSettings`
  - `jobs_status_worker.config.settings`
  - `jobs_status_worker.status.StatusProcessor`
  - `linx_shared.jobs.consumer.InvalidMessageError`
  - `linx_shared.jobs.consumer.run_consumer`
  - `linx_shared.jobs.broker.declare_topology`
  - `linx_shared.db.base.SessionLocal`, `engine`
- Produces:
  - `jobs_status_worker.health.check() -> None`
  - `jobs_status_worker.main._parse_status_event(body: bytes) -> JobStatusEvent`
  - `jobs_status_worker.main._wait_for_dependencies() -> None`
  - `jobs_status_worker.main.build_status_callback(processor: StatusProcessor) -> Callable[[bytes], None]`
  - `jobs_status_worker.main.build_consumer_threads(settings: StatusWorkerSettings, processor: StatusProcessor, stop_event: threading.Event) -> list[threading.Thread]`
  - `jobs_status_worker.main.main() -> None`

- [ ] **Step 1: Escrever os testes de health e main (falhando)**

`tests/test_health.py`: copiar de
`services/jobs_worker/tests/test_health.py`, trocando o import para
`from jobs_status_worker import health`.

`tests/test_main.py`:

```python
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from linx_shared.jobs.constants import (
    JOB_TYPE_PROVISION_APPLICATION,
    PROVISIONING_STATUS_QUEUE,
    JobStatus,
)
from linx_shared.jobs.consumer import InvalidMessageError
from linx_shared.jobs.envelope import JobStatusEvent

from jobs_status_worker import main as main_module
from jobs_status_worker.config import StatusWorkerSettings


def _valid_settings(monkeypatch, **env):
    monkeypatch.setenv(
        "RABBITMQ_AMQP_URL",
        "amqp://linx:real-rabbit-pass@localhost:5672/",
    )
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return StatusWorkerSettings(_env_file=None)


def _event(job_id):
    return JobStatusEvent(
        job_id=job_id,
        type=JOB_TYPE_PROVISION_APPLICATION,
        status=JobStatus.RUNNING,
        attempt=1,
    )


def test_parse_valid_status_event():
    event = _event("00000000-0000-0000-0000-000000000001")

    parsed = main_module._parse_status_event(event.model_dump_json().encode())

    assert parsed == event


def test_malformed_status_event_is_invalid_message():
    with pytest.raises(InvalidMessageError):
        main_module._parse_status_event(b'{"job_id": "not-a-uuid"}')


def test_status_callback_parses_and_processes():
    processed = []
    processor = MagicMock()
    processor.process.side_effect = processed.append
    callback = main_module.build_status_callback(processor)
    event = _event("00000000-0000-0000-0000-000000000001")

    callback(event.model_dump_json().encode())

    assert processed == [event]


def test_build_consumer_threads_uses_status_queue_and_concurrency(
    monkeypatch,
):
    settings = _valid_settings(monkeypatch, STATUS_CONCURRENCY="3")
    threads = main_module.build_consumer_threads(
        settings, MagicMock(), main_module.threading.Event()
    )

    assert len(threads) == 3
    assert [thread.name for thread in threads] == [
        "status-consumer-0",
        "status-consumer-1",
        "status-consumer-2",
    ]
    assert all(
        getattr(thread, "_args")[0] == PROVISIONING_STATUS_QUEUE
        for thread in threads
    )
    assert all(thread.daemon is True for thread in threads)


def test_wait_for_dependencies_retries_then_succeeds(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module, "check", lambda: calls.append("check"))
    engine = MagicMock()
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module.time, "sleep", lambda _: None)

    main_module._wait_for_dependencies()

    assert calls == ["check"]
    engine.connect.assert_called_once()


def test_wait_for_dependencies_raises_after_all_attempts(monkeypatch):
    attempts = []

    def failing_check():
        attempts.append(1)
        raise RuntimeError("db down")

    monkeypatch.setattr(main_module, "check", failing_check)
    monkeypatch.setattr(main_module.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="dependencies did not become ready"):
        main_module._wait_for_dependencies()

    assert len(attempts) == main_module.READY_ATTEMPTS


def test_main_starts_threads_and_stops(monkeypatch):
    import threading

    settings = SimpleNamespace(
        status_queue=PROVISIONING_STATUS_QUEUE,
        status_concurrency=1,
        status_prefetch=4,
        rabbitmq_amqp_url="amqp://linx:real-rabbit-pass@localhost:5672/",
    )
    stop_event = threading.Event()
    stop_event.set()
    created = []

    class FakeThread:
        def __init__(self, *args, **kwargs):
            self.started = False
            self.joined = False
            created.append(self)

        def start(self):
            self.started = True

        def join(self, timeout=None):
            self.joined = True

    monkeypatch.setattr(
        main_module, "StatusWorkerSettings", lambda: settings
    )
    monkeypatch.setattr(main_module, "SessionLocal", MagicMock())
    monkeypatch.setattr(main_module, "_wait_for_dependencies", lambda: None)
    monkeypatch.setattr(main_module, "_declare_topology", lambda *a: None)
    monkeypatch.setattr(main_module.threading, "Event", lambda: stop_event)
    monkeypatch.setattr(main_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(main_module.signal, "signal", lambda *a: None)

    main_module.main()

    assert len(created) == 1
    assert created[0].started is True
    assert created[0].joined is True
```

- [ ] **Step 2: Rodar os testes para ver falhar**

```bash
cd linx_core
poetry -C services/jobs_status_worker run pytest tests/test_health.py tests/test_main.py -q
```

Expected: FAIL com `ModuleNotFoundError` para `jobs_status_worker.health`/`main`.

- [ ] **Step 3: Implementar `health.py`**

Copiar `services/jobs_worker/src/jobs_worker/health.py`, trocando o import de
settings para `from jobs_status_worker.config import settings`.

- [ ] **Step 4: Implementar `main.py`**

Estrutura obrigatória:

```python
READY_ATTEMPTS = 30
READY_DELAY_SECONDS = 2


def _wait_for_dependencies() -> None:
    # loop de até READY_ATTEMPTS: check(); SELECT 1 FROM jobs LIMIT 1;
    # em sucesso loga e retorna; em falha loga warning e dorme
    # READY_DELAY_SECONDS; ao esgotar, RuntimeError
    # "dependencies did not become ready".


def _declare_topology(url: str, queue: str) -> None:
    # BlockingConnection + declare_topology(channel, queue), fechando sempre


def _parse_status_event(body: bytes) -> JobStatusEvent:
    # JobStatusEvent.model_validate_json; ValidationError vira
    # InvalidMessageError("invalid status event")


def build_status_callback(processor: StatusProcessor) -> Callable[[bytes], None]:
    # retorna callback que faz processor.process(_parse_status_event(body))


def build_consumer_threads(
    settings: StatusWorkerSettings,
    processor: StatusProcessor,
    stop_event: threading.Event,
) -> list[threading.Thread]:
    # para index em range(settings.status_concurrency), cria Thread(
    # target=run_consumer,
    # args=(settings.status_queue, callback,
    #       settings.rabbitmq_amqp_url, settings.status_prefetch,
    #       stop_event),
    # kwargs={"declare": declare},
    # name=f"status-consumer-{index}", daemon=True)
    # onde declare(channel) chama declare_topology(channel,
    # settings.status_queue)


def main() -> None:
    # logging.basicConfig no formato do jobs_worker;
    # settings = StatusWorkerSettings(); processor = StatusProcessor(SessionLocal);
    # _wait_for_dependencies(); _declare_topology(...);
    # stop_event = threading.Event();
    # threads = build_consumer_threads(settings, processor, stop_event);
    # SIGTERM/SIGINT setam stop_event;
    # start em todas, wait(1.0) até stop, join(timeout=5.0),
    # logs "jobs status worker started/stopped"
```

Não importar `linx_shared.jobs.broker.RabbitMQPublisher`, outbox, reaper,
leader election ou gRPC. Não criar `status_processor` dentro de callback por
mensagem: um único `StatusProcessor` é compartilhado pelas threads (ele abre
uma sessão por `process`).

- [ ] **Step 5: Rodar testes e lint**

```bash
cd linx_core
poetry -C services/jobs_status_worker run pytest -q
poetry -C services/jobs_status_worker run black --check src tests
poetry -C services/jobs_status_worker run isort --check-only src tests
poetry -C services/jobs_status_worker run flake8 src tests
poetry -C services/jobs_status_worker run mypy src tests
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add linx_core/services/jobs_status_worker/src/jobs_status_worker/health.py \
  linx_core/services/jobs_status_worker/src/jobs_status_worker/main.py \
  linx_core/services/jobs_status_worker/tests/test_health.py \
  linx_core/services/jobs_status_worker/tests/test_main.py
git commit -m "feat(jobs_status_worker): consome linx.jobs.status em processo próprio (#232)"
```

---

### Task 5: Remover o consumo de status do `jobs_worker`

**Files:**
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/main.py`
- Delete: `linx_core/services/jobs_worker/src/jobs_worker/status.py`
- Delete: `linx_core/services/jobs_worker/tests/test_status_processor.py`
- Modify: `linx_core/services/jobs_worker/tests/test_runtime.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `jobs_worker` passa a consumir apenas a fila de comandos.

- [ ] **Step 1: Remover a fiação de status do `main.py`**

Remover:
- import de `PROVISIONING_STATUS_QUEUE`;
- import de `StatusProcessor` e `JobStatusEvent`/`_parse_status_event`;
- `status_processor = StatusProcessor(...)`;
- `status_callback`;
- o `threading.Thread` do `status-consumer`.

Manter `_parse_envelope`, outbox relay, reaper e consumidores de comando.

- [ ] **Step 2: Deletar arquivos e teste obsoleto**

```bash
git rm linx_core/services/jobs_worker/src/jobs_worker/status.py \
  linx_core/services/jobs_worker/tests/test_status_processor.py
```

Remover de `tests/test_runtime.py` o teste
`test_malformed_status_event_is_invalid_message` e o import de
`_parse_status_event`.

- [ ] **Step 3: Verificar que não sobrou status no worker**

```bash
grep -R "StatusProcessor\|_parse_status_event\|PROVISIONING_STATUS_QUEUE\|status-consumer" \
  linx_core/services/jobs_worker/src linx_core/services/jobs_worker/tests
```

Expected: nenhuma saída.

- [ ] **Step 4: Rodar testes e lint**

```bash
cd linx_core
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://linx@127.0.0.1:5432/linx}" \
  poetry -C services/jobs_worker run pytest -q
poetry -C services/jobs_worker run black --check src tests
poetry -C services/jobs_worker run isort --check-only src tests
poetry -C services/jobs_worker run flake8 src tests
poetry -C services/jobs_worker run mypy src tests
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add linx_core/services/jobs_worker/src/jobs_worker/main.py \
  linx_core/services/jobs_worker/src/jobs_worker/status.py \
  linx_core/services/jobs_worker/tests/test_status_processor.py \
  linx_core/services/jobs_worker/tests/test_runtime.py
git commit -m "refactor(jobs_worker): remove consumo de status do worker de domínio (#232)"
```

---

### Task 6: Dockerfile do `jobs_status_worker`

**Files:**
- Create: `linx_core/services/jobs_status_worker/Dockerfile`

**Interfaces:**
- Consumes: `linx_core/shared/`, `linx_core/services/jobs_status_worker/`.
- Produces: imagem que executa `python -m jobs_status_worker.main`.

- [ ] **Step 1: Criar o Dockerfile**

Modelar em `services/jobs_worker/Dockerfile`, substituindo o serviço:

```dockerfile
# --- STAGE 1: Builder ---
FROM python:3.12.10-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.4.1

COPY shared ./shared
COPY services/jobs_status_worker ./services/jobs_status_worker

RUN poetry -C services/jobs_status_worker config virtualenvs.in-project true \
    && poetry -C services/jobs_status_worker install --without dev --no-interaction --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.12.10-slim AS runtime

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY --from=builder /app/shared ./shared
COPY --from=builder /app/services/jobs_status_worker ./services/jobs_status_worker

ENV PATH="/app/services/jobs_status_worker/.venv/bin:$PATH" \
    PYTHONPATH=/app/services/jobs_status_worker/src:/app/shared/src

RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["python", "-c", "from jobs_status_worker.health import check; check()"]

CMD ["python", "-m", "jobs_status_worker.main"]
```

- [ ] **Step 2: Buildar e validar a imagem**

```bash
docker build \
  -f linx_core/services/jobs_status_worker/Dockerfile \
  -t jobs-status-worker:local \
  linx_core
docker run --rm \
  -e DATABASE_URL=postgresql+psycopg://linx@127.0.0.1:5432/linx \
  -e RABBITMQ_AMQP_URL=amqp://linx:real-rabbit-pass@127.0.0.1:5672/ \
  jobs-status-worker:local \
  python -c "import jobs_status_worker.main; print('ok')"
```

Expected: build conclui e imprime `ok`.

- [ ] **Step 3: Commit**

```bash
git add linx_core/services/jobs_status_worker/Dockerfile
git commit -m "feat(jobs_status_worker): adiciona Dockerfile próprio (#232)"
```

---

### Task 7: Compose de desenvolvimento e `run.sh`

**Files:**
- Modify: `linx_core/docker-compose.yml`
- Modify: `linx_core/scripts/run.sh`

**Interfaces:**
- Consumes: imagem/Dockerfile da Task 6; `STATUS_QUEUE`, `STATUS_CONCURRENCY`, `STATUS_PREFETCH`.
- Produces: serviço `jobs_status_worker` no compose dev e no runner local.

- [ ] **Step 1: Adicionar o serviço ao compose**

Após o bloco `jobs_worker` em `linx_core/docker-compose.yml`:

```yaml
  jobs_status_worker:
    build:
      context: .
      dockerfile: services/jobs_status_worker/Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      - DATABASE_URL=postgresql+psycopg://${POSTGRES_USER:-linx}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}@db:5432/${POSTGRES_DB:-linx}
      - RABBITMQ_AMQP_URL=amqp://${RABBITMQ_ADMIN_USER:-linx}:${RABBITMQ_ADMIN_PASSWORD:?RABBITMQ_ADMIN_PASSWORD must be set}@rabbitmq:5672/
      - STATUS_QUEUE=${STATUS_QUEUE:-linx.jobs.status}
      - STATUS_CONCURRENCY=${STATUS_CONCURRENCY:-2}
      - STATUS_PREFETCH=${STATUS_PREFETCH:-4}
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "from jobs_status_worker.health import check; check()"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

- [ ] **Step 2: Adicionar ao `run.sh`**

Atualizar o cabeçalho para citar o novo serviço e, após o launch do
`jobs_worker`, adicionar:

```bash
echo "Subindo jobs_status_worker (RabbitMQ)..."
poetry -C services/jobs_status_worker run python -m jobs_status_worker.main &
pids+=("$!")
```

- [ ] **Step 3: Validar compose e script**

```bash
cd linx_core
docker compose config --quiet
bash -n scripts/run.sh
```

Expected: sem erro de configuração nem de sintaxe.

- [ ] **Step 4: Subir apenas o novo serviço e conferir health/logs**

```bash
cd linx_core
docker compose up -d --build db rabbitmq jobs_status_worker
docker compose ps jobs_status_worker
docker compose logs --tail=50 jobs_status_worker
```

Expected: container `healthy` (após o start period), log
`jobs status worker started (queue=linx.jobs.status ...)` e nenhum traceback.

- [ ] **Step 5: Commit**

```bash
git add linx_core/docker-compose.yml linx_core/scripts/run.sh
git commit -m "chore(devops): sobe jobs_status_worker no compose e run.sh (#232)"
```

---

### Task 8: Manifestos Kubernetes e asserts

**Files:**
- Create: `infra/kubernetes/base/jobs-status-worker.yaml`
- Modify: `infra/kubernetes/base/kustomization.yaml`
- Modify: `infra/kubernetes/overlays/ecr/kustomization.yaml`
- Modify: `.github/workflows/k8s-ci.yml`

**Interfaces:**
- Consumes: imagem `includeluisferreira/jobs-status-worker:dev`; ConfigMap `linx-config`; Secret `linx-secrets`.
- Produces: Deployment `jobs-status-worker` com 2 réplicas, apenas consumidor (sem Service/Lease).

- [ ] **Step 1: Criar o Deployment**

`infra/kubernetes/base/jobs-status-worker.yaml`:

```yaml
# Consumidor de eventos de status (#232). Não precisa de ServiceAccount,
# Lease ou Service: não recebe tráfego e escala horizontalmente com segurança
# porque apply_status_event é idempotente.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jobs-status-worker
  namespace: linx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: jobs-status-worker
  template:
    metadata:
      labels:
        app: jobs-status-worker
    spec:
      initContainers:
        - name: wait-for-db
          image: includeluisferreira/jobs-status-worker:dev
          imagePullPolicy: Always
          command:
            - python
            - -m
            - linx_shared.db.wait
          envFrom:
            - configMapRef:
                name: linx-config
            - secretRef:
                name: linx-secrets
      containers:
        - name: jobs-status-worker
          image: includeluisferreira/jobs-status-worker:dev
          imagePullPolicy: Always
          envFrom:
            - configMapRef:
                name: linx-config
            - secretRef:
                name: linx-secrets
```

- [ ] **Step 2: Registrar no kustomization e no overlay ECR**

Adicionar `- jobs-status-worker.yaml` à lista `resources` de
`infra/kubernetes/base/kustomization.yaml`.

Em `infra/kubernetes/overlays/ecr/kustomization.yaml`, adicionar:

```yaml
  - name: includeluisferreira/jobs-status-worker
    newName: <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/jobs-status-worker
    newTag: sha-<SHORT_SHA>
```

- [ ] **Step 3: Adicionar assert no `k8s-ci.yml`**

No step `Render base manifests`, após os asserts existentes:

```yaml
          # Status worker roda isolado, sem leader election (#232).
          echo "$out" | grep -q "name: jobs-status-worker"
          echo "$out" | grep -q "replicas: 2"
```

- [ ] **Step 4: Validar render**

```bash
kubectl kustomize infra/kubernetes >/tmp/linx-k8s.yaml
grep -q "name: jobs-status-worker" /tmp/linx-k8s.yaml
kubectl kustomize infra/kubernetes/overlays/dockerhub >/dev/null
kubectl kustomize infra/kubernetes/overlays/ecr >/dev/null
```

Expected: todos os comandos com exit 0. Se `kubectl` não estiver instalado,
validar o YAML com `python -c "import yaml,sys; yaml.safe_load(open(...))"` e
registrar a limitação no relatório.

- [ ] **Step 5: Commit**

```bash
git add infra/kubernetes/base/jobs-status-worker.yaml \
  infra/kubernetes/base/kustomization.yaml \
  infra/kubernetes/overlays/ecr/kustomization.yaml \
  .github/workflows/k8s-ci.yml
git commit -m "chore(deploy): adiciona Deployment jobs-status-worker (#232)"
```

---

### Task 9: CI e publicação de imagem

**Files:**
- Modify: `.github/workflows/backend-ci.yml`
- Create: `.github/workflows/publish-jobs-status-worker-image.yml`

**Interfaces:**
- Consumes: pacote da Task 2, Dockerfile da Task 6, reusable `publish-linx-core-image.yml`.
- Produces: lint/test do novo pacote e publicação de `includeluisferreira/jobs-status-worker`.

- [ ] **Step 1: Adicionar o pacote ao `backend-ci.yml`**

Nas duas matrizes (`lint` e `test`), incluir
`services/jobs_status_worker` na lista `package`. No step de instalação de
dependências, adicionar:

```yaml
          poetry -C services/jobs_status_worker install
```

- [ ] **Step 2: Criar o workflow de publicação**

`.github/workflows/publish-jobs-status-worker-image.yml`, modelado em
`publish-jobs-worker-image.yml`:

```yaml
name: Publish Jobs Status Worker Image

on:
  push:
    branches:
      - develop
      - main
    paths:
      - "linx_core/services/jobs_status_worker/**"
      - "linx_core/shared/**"
      - ".github/workflows/publish-jobs-status-worker-image.yml"
      - ".github/workflows/publish-linx-core-image.yml"
  pull_request:
    paths:
      - "linx_core/services/jobs_status_worker/**"
      - "linx_core/shared/**"
      - ".github/workflows/publish-jobs-status-worker-image.yml"
      - ".github/workflows/publish-linx-core-image.yml"
  workflow_dispatch:

jobs:
  publish:
    uses: ./.github/workflows/publish-linx-core-image.yml
    with:
      service: jobs_status_worker
      dockerfile: linx_core/services/jobs_status_worker/Dockerfile
      repository: includeluisferreira/jobs-status-worker
      context: linx_core
      push: ${{ github.event_name != 'pull_request' }}
    secrets:
      DOCKERHUB_USERNAME: ${{ secrets.DOCKERHUB_USERNAME }}
      DOCKERHUB_TOKEN: ${{ secrets.DOCKERHUB_TOKEN }}
```

- [ ] **Step 3: Validar YAML e rodar os testes dos dois pacotes**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/backend-ci.yml')); yaml.safe_load(open('.github/workflows/publish-jobs-status-worker-image.yml'))"
cd linx_core
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://linx@127.0.0.1:5432/linx}" \
  poetry -C services/jobs_worker run pytest -q
poetry -C services/jobs_status_worker run pytest -q
```

Expected: YAML válido e testes PASS.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/backend-ci.yml \
  .github/workflows/publish-jobs-status-worker-image.yml
git commit -m "ci: testa e publica a imagem jobs-status-worker (#232)"
```

---

### Task 10: Atualizar documentação

**Files:**
- Modify: `linx_core/README.md`
- Modify: `infra/kubernetes/README.md`

**Interfaces:**
- Consumes: nomes e comportamento definidos nas tasks anteriores.
- Produces: documentação sem a afirmação de que o status roda no mesmo worker.

- [ ] **Step 1: Atualizar `linx_core/README.md`**

Ajustar, no mínimo:
- árvore de serviços (linhas ~30-33) e lista do compose (linha ~46) para incluir
  `jobs_status_worker/` e `services/jobs_status_worker/`;
- diagrama/fluxo (linhas ~58-64) e passo 5 do fluxo (linha ~145) para dizer que
  o `jobs_status_worker` consome `linx.jobs.status` e persiste o estado final;
- comandos de instalação/execução (linhas ~282-313) para incluir
  `poetry -C services/jobs_status_worker install` e
  `poetry -C services/jobs_status_worker run python -m jobs_status_worker.main`;
- tabela de variáveis (linhas ~435-441) com `STATUS_QUEUE` (`linx.jobs.status`),
  `STATUS_CONCURRENCY` (`2`) e `STATUS_PREFETCH` (`4`);
- qualquer menção a "o mesmo worker consome `linx.jobs.status`" deve ser
  removida.

- [ ] **Step 2: Atualizar `infra/kubernetes/README.md`**

Ajustar:
- tabela de imagens (linha ~33-37) com `jobs-status-worker` →
  `includeluisferreira/jobs-status-worker:dev`;
- tabela de workflows de publicação (linha ~258) com
  `publish-jobs-status-worker-image.yml`;
- tabela de paths → serviço (linhas ~265-274): adicionar coluna
  `jobs-status-worker` e marcar `linx_core/services/jobs_status_worker/**` e
  `linx_core/shared/**`; manter o comportamento existente das outras colunas;
- contagem de pods (linha ~376) para incluir `2x jobs-status-worker`;
- menção a `RABBITMQ_AMQP_URL` (linha ~148) deve citar os dois workers;
- fallback offline (linha ~453) com o novo nome de imagem.

- [ ] **Step 3: Verificar que não restaram afirmações antigas**

```bash
grep -rn "mesmo worker consome\|o mesmo worker" linx_core/README.md
grep -n "jobs-status-worker" infra/kubernetes/README.md
```

Expected: o primeiro grep sem saída; o segundo lista as novas referências.

- [ ] **Step 4: Commit**

```bash
git add linx_core/README.md infra/kubernetes/README.md
git commit -m "docs: documenta o jobs_status_worker separado (#232)"
```

---

### Task 11: Validação final e smoke de isolamento

**Files:**
- Nenhum arquivo novo; corrigir apenas arquivos das tasks anteriores se algum
  passo falhar.

**Interfaces:**
- Consumes: tudo das tasks 1-10.
- Produces: evidência de que o status worker consome a fila isoladamente e de
  que o `jobs_worker` não consome mais status.

- [ ] **Step 1: Rodar a bateria completa de lint/testes**

```bash
cd linx_core
poetry -C shared run pytest -q
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://linx@127.0.0.1:5432/linx}" \
  poetry -C services/jobs_worker run pytest -q
poetry -C services/jobs_status_worker run pytest -q
poetry -C services/jobs_status_worker run pytest --cov=src --cov-fail-under=70 -q
```

Expected: PASS e cobertura `>=70%` no pacote novo.

- [ ] **Step 2: Subir a stack dev**

```bash
cd linx_core
docker compose up -d --build db rabbitmq identity_api jobs_worker jobs_status_worker
docker compose ps
```

Expected: `identity_api`, `jobs_worker` e `jobs_status_worker` saudáveis.

- [ ] **Step 3: Smoke do fluxo 202 → outbox → RabbitMQ → status aplicado**

Criar um provisionamento pela `identity_api` (tenant e aplicação válidos,
conforme README) e verificar:

```bash
cd linx_core
docker compose logs --tail=100 jobs_worker | grep -E "job|provision"
docker compose logs --tail=100 jobs_status_worker | grep "status event processed"
```

Expected: o `jobs_worker` emite o evento; o `jobs_status_worker` loga
`status event processed` para o `job_id`, com `status=succeeded` ou `failed`.

- [ ] **Step 4: Provar isolamento sem o `jobs_worker`**

```bash
cd linx_core
docker compose stop jobs_worker
# Use um job_id real e attempt igual a jobs.attempts do job.
export SMOKE_JOB_ID="<job-id-real>"
export SMOKE_ATTEMPT="<attempts-do-job>"
poetry -C services/jobs_worker run python - <<'PY'
import os

from linx_shared.jobs.broker import RabbitMQPublisher
from linx_shared.jobs.constants import (
    JOB_EVENTS_EXCHANGE,
    JOB_TYPE_PROVISION_APPLICATION,
    JobStatus,
)
from linx_shared.jobs.envelope import JobStatusEvent

event = JobStatusEvent(
    job_id=os.environ["SMOKE_JOB_ID"],
    type=JOB_TYPE_PROVISION_APPLICATION,
    status=JobStatus.RUNNING,
    attempt=int(os.environ["SMOKE_ATTEMPT"]),
)
publisher = RabbitMQPublisher(os.environ["RABBITMQ_AMQP_URL"])
publisher.publish(
    JOB_EVENTS_EXCHANGE,
    f"{JOB_TYPE_PROVISION_APPLICATION}.started",
    event.model_dump(mode="json"),
)
publisher.close()
PY
docker compose logs --tail=50 jobs_status_worker | grep "status event processed"
```

Expected: o status worker aplica e faz ack mesmo com o worker de domínio
parado.

- [ ] **Step 5: Confirmar que o `jobs_worker` não consome mais status**

```bash
cd linx_core
docker compose start jobs_worker
docker compose logs --tail=50 jobs_worker
grep -R "status-consumer" services/jobs_worker/src
```

Expected: nenhum log de status no `jobs_worker` e grep sem saída.

- [ ] **Step 6: Registrar evidências no relatório final**

Documentar: comandos executados, resultados reais, cobertura, logs do smoke e
qualquer pendência (ex.: `kubectl` ausente no ambiente local). Não declarar
sucesso sem a saída correspondente.

---

## Self-Review

- **Cobertura da spec:** pacote próprio (Tasks 2-4), consumidor compartilhado
  (Task 1), remoção do status do `jobs_worker` (Task 5), Dockerfile (Task 6),
  compose/run.sh (Task 7), Kubernetes + ECR (Task 8), CI/publish (Task 9),
  docs (Task 10) e validação de isolamento (Task 11).
- **Modos de falha do Review Focus:** mensagem venenosa (Task 1), evento
  duplicado/atrasado (Task 3), dependências indisponíveis (Task 4), config
  mínima (Task 2), fila padrão/vazia (Tasks 2 e 4).
- **Consistência de tipos:** `StatusWorkerSettings` com
  `status_queue`/`status_concurrency`/`status_prefetch`;
  `build_consumer_threads(settings, processor, stop_event)`;
  `build_status_callback(processor)`; nomes de env `STATUS_QUEUE`,
  `STATUS_CONCURRENCY`, `STATUS_PREFETCH`; imagem
  `includeluisferreira/jobs-status-worker`.
- **Proporção:** o plano fixa assinaturas, valores e testes; corpos de
  algoritmo ficam para o implementador.
