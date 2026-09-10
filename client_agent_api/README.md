# Client Agent API

Middleware de segurança/roteamento do **Aluno 3** — um dos dois módulos do
tenant implantado por aplicação (Sprint 4). Este é o scaffold inicial com
FastAPI + Poetry, entregue na issue #16.

## 📋 O que foi feito

- [x] Scaffold do serviço com **FastAPI** (`0.141.x`) + **Uvicorn** (`0.52.x`).
- [x] Estrutura `src/agent/` com `main.py` (`app = FastAPI()`) e `GET /health`.
- [x] Teste de smoke (`tests/test_main.py`) validando `/health`.
- [x] Tooling de dev espelhado do `saas_backend`: `black`, `isort`, `flake8`,
      `mypy`, `pytest` + `pytest-cov`, `taskipy` e `httpx2`.
- [x] `Dockerfile` mínimo (`python:3.12-slim` + poetry + uvicorn).

## 📍 Endpoints

| Método | Rota      | Descrição                                |
| :----: | --------- | ---------------------------------------- |
| `GET`  | `/health` | Health check retornando `{"status":"ok"}` |

## 📁 Estrutura

| Arquivo                       | Responsabilidade                                |
| ----------------------------- | ----------------------------------------------- |
| `pyproject.toml`              | Dependências, pacote `agent` e tasks de dev.    |
| `poetry.lock`                 | Versões travadas das dependências.              |
| `src/agent/main.py`           | Aplicação FastAPI (`app`) e endpoint `/health`. |
| `tests/test_main.py`          | Smoke test do `/health` com `TestClient`.       |
| `Dockerfile`                  | Imagem mínima para rodar o serviço.             |

## ⚙️ Instalação

```bash
poetry install
```

## ▶️ Executando

```bash
poetry run uvicorn agent.main:app --reload
```

Verificação:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

## 🧪 Testes

```bash
poetry run pytest
```

## 🛠️ Lint e tipos

```bash
task lint          # black + isort + mypy + flake8
```

## 🐳 Docker

```bash
docker build -t client-agent-api .
docker run --rm -p 8000:8000 client-agent-api
```
