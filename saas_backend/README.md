# SaaS Backend

Backend do SaaS desenvolvido em Python utilizando FastAPI, com gerenciamento de dependências através do Poetry e ferramentas de qualidade e testes.

## 📋 O que foi feito

* [x] Instalação do Poetry.
* [x] Instalação das dependências Python.
* [x] Configuração das ferramentas de qualidade de código.
* [x] Configuração do ambiente de testes.
* [x] Configuração de coverage de testes.
* [x] Configuração do Isort.
* [x] Início da API FastAPI (`linx.main:app`).
* [x] Endpoint de health check (`/health`).
* [x] Página inicial servida via Jinja2 + arquivos estáticos (`/`).

## 📍 Endpoints disponíveis

| Método | Rota      | Descrição                                  |
| ------ | --------- | ------------------------------------------ |
| GET    | `/`       | Página inicial "Em Construção" (HTML).     |
| GET    | `/health` | Health check retornando `{"status": "ok"}`. |
| GET    | `/docs`   | Documentação interativa (Swagger UI).      |
| GET    | `/redoc`  | Documentação alternativa (ReDoc).          |

## ⚙️ Instalação

Instale as dependências:

```bash
poetry install
```

## ▶️ Executando o projeto

Para iniciar o servidor FastAPI utilizando o Uvicorn:

```bash
poetry run uvicorn linx.main:app --reload
```

O parâmetro `--reload` habilita o recarregamento automático do servidor durante o desenvolvimento.

## 🧪 Testes

Para executar os testes:

```bash
task test
```

Também é possível executar o Pytest diretamente:

```bash
pytest
```

### Testando endpoints

Para testar um endpoint diretamente pelo terminal:

```bash
curl http://localhost:8000/health
```

## 🛠️ Dependências de desenvolvimento

### Pytest

Framework para testes automatizados em Python. Permite escrever e executar testes unitários e de integração de forma simples e escalável.

### Black

Formatador automático de código Python (*uncompromising code formatter*). Aplica regras consistentes de formatação ao código.

### Flake8

Linter para Python que realiza análise estática do código, identificando problemas como erros de sintaxe, variáveis não utilizadas e violações das convenções da PEP 8.

### Mypy

Verificador estático de tipos para Python. Analisa as anotações de tipo (*type hints*) para identificar possíveis erros de compatibilidade e problemas de lógica antes da execução do código.

### httpx2

Client HTTP de próxima geração, utilizado pelo `TestClient` do FastAPI/Starlette para os testes de endpoints. Este projeto usa `httpx2` (sucessor do `httpx`), que é a dependência exigida pela versão atual do Starlette para o módulo `starlette.testclient`.

### Taskipy

Task runner para Python que permite criar atalhos para comandos utilizados frequentemente no projeto.

