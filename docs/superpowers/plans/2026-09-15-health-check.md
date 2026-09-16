# GET /health (DB + gRPC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender `GET /health` para reportar o status do banco (via `SELECT 1`) e do servidor gRPC (via sonda TCP na porta configurada), retornando `200` quando ambos estão ok e `503` + `"status":"degraded"` quando qualquer um falha.

**Architecture:** O helper `is_grpc_serving()` vive em `src/linx/grpc_server.py` (co-localizado com o servidor gRPC) e faz uma conexão TCP de curta duração em `settings.grpc_host:settings.grpc_port`, normalizando endereços de bind (`0.0.0.0`/`::` → `127.0.0.1`) e tratando `port=0`. O endpoint em `src/linx/main.py` recebe a sessão via `Depends(get_db)`, executa `SELECT 1` e ajusta o `status_code` da resposta. Ambos os checks são testáveis de forma isolada (monkeypatch do helper / override da dependência).

**Tech Stack:** FastAPI 0.141, SQLAlchemy 2.0, grpcio, pytest, black/isort/flake8/mypy, Poetry.

**Base branch:** `develop` (a issue #28 / PR #156 já foi mergeada, `grpc_server.py` está disponível).

**Branch de trabalho:** `issue29_health_check`.

---

## File Structure

| Arquivo | Ação | Responsabilidade |
| --- | --- | --- |
| `saas_backend/src/linx/grpc_server.py` | Modificar | Adicionar `is_grpc_serving(host, port, timeout)`. |
| `saas_backend/src/linx/main.py` | Modificar | `GET /health` checando DB + gRPC e retornando 200/503. |
| `saas_backend/tests/test_grpc.py` | Modificar | Testes unitários de `is_grpc_serving`; ajustar teste do lifespan. |
| `saas_backend/tests/test_main.py` | Modificar | Testes dos três cenários de `/health`. |
| `saas_backend/README.md` | Modificar | Documentar corpo/status do `/health`. |
| `docs/openapi-stub.json` | Possivelmente modificar | Manter o stub igual ao `app.openapi()` (verificar Task 3). |

---

## Task 0: Criar a branch a partir da `develop`

**Files:** nenhum.

- [ ] **Step 1: Atualizar a develop e criar a branch**

```bash
git checkout develop
git pull origin develop
git checkout -b issue29_health_check
```

Expected: `Switched to a new branch 'issue29_health_check'` e `grpc_server.py` presente em `saas_backend/src/linx/`.

- [ ] **Step 2: Confirmar a base limpa**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

---

## Task 1: Helper `is_grpc_serving()`

**Files:**
- Modify: `saas_backend/src/linx/grpc_server.py`
- Test: `saas_backend/tests/test_grpc.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicione no topo de `saas_backend/tests/test_grpc.py`, junto aos imports existentes:

```python
import socket
```

Ajuste o import do módulo gRPC para incluir o helper:

```python
from linx.grpc_server import AgentBridgeServicer, create_server, is_grpc_serving
```

Adicione ao final de `tests/test_grpc.py`:

```python
def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_is_grpc_serving_true_when_port_is_open():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    try:
        assert is_grpc_serving(host="127.0.0.1", port=port) is True
    finally:
        listener.close()


def test_is_grpc_serving_false_when_port_is_closed():
    port = _free_port()

    assert is_grpc_serving(host="127.0.0.1", port=port) is False


def test_is_grpc_serving_false_when_port_is_zero():
    assert is_grpc_serving(host="127.0.0.1", port=0) is False


def test_is_grpc_serving_normalizes_wildcard_host(monkeypatch):
    listener = socket.socket()
    listener.bind(("0.0.0.0", 0))
    listener.listen()
    port = listener.getsockname()[1]
    monkeypatch.setattr(settings, "grpc_host", "0.0.0.0")
    monkeypatch.setattr(settings, "grpc_port", port)
    try:
        assert is_grpc_serving() is True
    finally:
        listener.close()
```

- [ ] **Step 2: Rodar os testes e verificar que falham**

Run: `poetry run pytest tests/test_grpc.py -k is_grpc_serving -v`
Expected: FAIL com `ImportError: cannot import name 'is_grpc_serving'`.

- [ ] **Step 3: Implementar o helper**

Em `saas_backend/src/linx/grpc_server.py`, adicione `import socket` após `import logging` (ordem isort: stdlib em bloco alfabético → `import logging` e `import socket`):

```python
import logging
import socket
from concurrent import futures
from uuid import UUID
```

Adicione a função antes de `def serve():` (após `create_server`):

```python
def is_grpc_serving(
    host: str | None = None,
    port: int | None = None,
    timeout: float = 1.0,
) -> bool:
    """Indica se há um servidor escutando no host/porta do gRPC."""
    target_host = host or settings.grpc_host
    target_port = settings.grpc_port if port is None else port
    if target_host in ("", "0.0.0.0", "::"):
        target_host = "127.0.0.1"
    if target_port == 0:
        return False
    try:
        with socket.create_connection(
            (target_host, target_port), timeout=timeout
        ):
            return True
    except OSError:
        return False
```

- [ ] **Step 4: Rodar os testes e verificar que passam**

Run: `poetry run pytest tests/test_grpc.py -k is_grpc_serving -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add saas_backend/src/linx/grpc_server.py saas_backend/tests/test_grpc.py
git commit -m "feat(health): adiciona is_grpc_serving para sondar a porta do gRPC"
```

---

## Task 2: Endpoint `GET /health`

**Files:**
- Modify: `saas_backend/src/linx/main.py`
- Test: `saas_backend/tests/test_main.py`

- [ ] **Step 1: Escrever os testes que falham**

Substitua todo o conteúdo de `saas_backend/tests/test_main.py` por:

```python
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from linx.db.base import get_db
from linx.main import app

client = TestClient(app)


class _OkSession:
    def execute(self, *args, **kwargs):
        return None


class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise SQLAlchemyError("banco indisponível")


def _override_db(session) -> None:
    app.dependency_overrides[get_db] = lambda: session


def test_health_ok_when_db_and_grpc_are_up(monkeypatch):
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: True)
    _override_db(_OkSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "grpc": True}


def test_health_degraded_when_grpc_is_down(monkeypatch):
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: False)
    _override_db(_OkSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "db": True,
        "grpc": False,
    }


def test_health_degraded_when_db_is_down(monkeypatch):
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: True)
    _override_db(_BrokenSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "db": False,
        "grpc": True,
    }


def test_home_html_response():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 2: Rodar os testes e verificar que falham**

Run: `poetry run pytest tests/test_main.py -v`
Expected: FAIL — `/health` retorna `{"status": "ok"}` sem as chaves `db`/`grpc` e sempre `200`.

- [ ] **Step 3: Implementar o endpoint**

Em `saas_backend/src/linx/main.py`, ajuste os imports para:

```python
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from linx.db.base import get_db
from linx.grpc_server import create_server, is_grpc_serving
from linx.routes.application import router as application_router
from linx.routes.tenant import router
```

Substitua o endpoint atual por:

```python
@app.get("/health")
async def health(
    response: Response, db: Session = Depends(get_db)
) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except SQLAlchemyError:
        db_ok = False

    grpc_ok = is_grpc_serving()
    healthy = db_ok and grpc_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "degraded",
        "db": db_ok,
        "grpc": grpc_ok,
    }
```

- [ ] **Step 4: Rodar os testes e verificar que passam**

Run: `poetry run pytest tests/test_main.py -v`
Expected: 4 passed.

- [ ] **Step 5: Ajustar o teste do lifespan em `tests/test_grpc.py`**

O teste `test_lifespan_starts_and_stops_grpc_server` usa um `MagicMock` como servidor (sem bind real) e hoje exige `/health` com status `200`. Monkeie o helper para manter a asserção:

```python
def test_lifespan_starts_and_stops_grpc_server(monkeypatch):
    fake_server = MagicMock()
    monkeypatch.setattr("linx.main.create_server", lambda: fake_server)
    monkeypatch.setattr("linx.main.is_grpc_serving", lambda: True)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        fake_server.start.assert_called_once()

    fake_server.stop.assert_called_once_with(grace=5)
    fake_server.stop.return_value.wait.assert_called_once()
```

- [ ] **Step 6: Rodar a suíte de gRPC e verificar que passa**

Run: `poetry run pytest tests/test_grpc.py -v`
Expected: todos os testes passam.

- [ ] **Step 7: Commit**

```bash
git add saas_backend/src/linx/main.py saas_backend/tests/test_main.py saas_backend/tests/test_grpc.py
git commit -m "feat(health): GET /health reporta status do banco e do gRPC"
```

---

## Task 3: OpenAPI stub e README

**Files:**
- Modify (se necessário): `docs/openapi-stub.json`
- Modify: `saas_backend/README.md`

- [ ] **Step 1: Verificar se o OpenAPI mudou**

Run: `poetry run pytest tests/test_openapi.py -v`
Expected: PASS. Se `test_openapi_stub_file_matches_live_spec` falhar, regenere o stub:

```bash
poetry run python -c "import json; from linx.main import app; open('../docs/openapi-stub.json','w').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')"
```

Depois rode o teste de novo e confirme que passa.

- [ ] **Step 2: Atualizar o README**

Na tabela de endpoints, altere a linha do `/health` para:

```markdown
|  `GET`  | `/health`                  | Health check: status do banco e do servidor gRPC (`200`/`503`). |
```

Na seção "Testando endpoints" (perto do fim do arquivo), substitua a resposta esperada por:

```markdown
```bash
curl -i http://localhost:8000/health
```

Resposta esperada (`200` quando banco e gRPC estão ok):

```json
{
  "status": "ok",
  "db": true,
  "grpc": true
}
```

Se o Postgres ou o servidor gRPC estiverem fora, retorna `503` com:

```json
{
  "status": "degraded",
  "db": false,
  "grpc": true
}
```
```

- [ ] **Step 3: Commit**

```bash
git add saas_backend/README.md docs/openapi-stub.json
git commit -m "docs(health): documenta status de banco e gRPC no /health"
```

---

## Task 4: Verificação completa

**Files:** nenhum.

- [ ] **Step 1: Lint + tipos**

Run: `task lint`
Expected: sem erros (black/isort aplicam; mypy e flake8 sem saída de erro).

- [ ] **Step 2: Testes + cobertura**

Run: `task test`
Expected: todos passam; cobertura `>= 70%`.

- [ ] **Step 3: Verificação manual (opcional, requer Postgres do compose)**

Run: `poetry run uvicorn linx.main:app` em um terminal e, em outro:

```bash
curl -i localhost:8000/health
```

Expected: `HTTP/1.1 200 OK` e `{"status":"ok","db":true,"grpc":true}`. Pare o Postgres (`docker stop infra-postgres-1`) e confirme `503`/`degraded` com `db:false`.

- [ ] **Step 4: Commit de eventuais ajustes de lint**

```bash
git add -A
git commit -m "style(health): ajustes de lint"
```

---

## Task 5: Code review

- [ ] **Step 1:** Invocar a skill `requesting-code-review` sobre o diff de `develop`.
- [ ] **Step 2:** Aplicar as correções apontadas (se houver) e repetir Task 4.

---

## Task 6: PR para a `develop` (somente após confirmação do usuário)

- [ ] **Step 1: Push**

```bash
git push -u origin issue29_health_check
```

- [ ] **Step 2: Abrir a PR**

```bash
gh pr create --base develop --title "feat(backend): GET /health (DB + gRPC server status)" --body "Closes #29"
```

Expected: URL da PR retornada.

---

## Self-Review

- **Cobertura da issue:** `/health` reporta `db` e `grpc` (Task 2); 200 com ambos ok (Task 2 Step 1); 503 + degraded quando um falha (Task 2 Step 1); `SELECT 1` (Task 2 Step 3); check do gRPC na porta 50051 (Task 1). ✔
- **Placeholders:** nenhum; todo passo tem código/comando e saída esperada. ✔
- **Consistência de tipos:** `is_grpc_serving(host, port, timeout) -> bool` definida na Task 1 e usada em `main.py` (Task 2) e nos testes. `get_db` é a dependência já existente em `linx.db.base`. ✔
- **Escopo:** única feature, um plano. ✔
