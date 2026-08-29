# SaaS Backend

Backend do SaaS desenvolvido em Python utilizando **FastAPI**, com gerenciamento de dependências através do **Poetry** e ferramentas de qualidade e testes.

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

| Método | Rota      | Descrição                                   |
| :----: | --------- | ------------------------------------------- |
|  `GET` | `/`       | Página inicial "Em Construção" (HTML).      |
|  `GET` | `/health` | Health check retornando `{"status": "ok"}`. |
|  `GET` | `/docs`   | Documentação interativa (Swagger UI).       |
|  `GET` | `/redoc`  | Documentação alternativa (ReDoc).           |

## ⚙️ Instalação

Instale as dependências do projeto:

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

Resposta esperada:

```json
{
  "status": "ok"
}
```

## 📦 Dependências do projeto

### FastAPI

Framework web moderno e de alto desempenho para a construção de APIs em Python, com validação automática de dados via Pydantic e documentação interativa (Swagger/ReDoc).

### Uvicorn

Servidor web ASGI de alta performance baseado em `uvloop` e `httptools`, utilizado para executar a aplicação FastAPI.

### Pydantic Settings

Extensão do Pydantic para gerenciamento de configurações e variáveis de ambiente da aplicação através de classes tipadas e validação estática.

### Jinja2

Motor de templates para Python, utilizado na renderização de páginas HTML dinâmicas no lado do servidor.

### SQLAlchemy

ORM (*Object-Relational Mapping*) e SQL Toolkit para abstração, consulta e manipulação de banco de dados relacional em Python.

### Psycopg

Adaptador de banco de dados PostgreSQL de terceira geração para Python, focado em alta performance, concorrência e recursos assíncronos.

## 🛠️ Dependências de desenvolvimento

### Pytest

Framework para testes automatizados em Python. Permite escrever e executar testes unitários e de integração de forma simples e escalável.

### Black

Formatador automático de código Python (*uncompromising code formatter*). Aplica regras consistentes de formatação ao código.

### Isort

Utilitário para ordenação e organização automática das declarações de `import` em ordem alfabética e por seções de dependência.

### Flake8

Linter para Python que realiza análise estática do código, identificando problemas como erros de sintaxe, variáveis não utilizadas e violações das convenções da PEP 8.

### Mypy

Verificador estático de tipos para Python. Analisa as anotações de tipo (*type hints*) para identificar possíveis erros de compatibilidade e problemas de lógica antes da execução do código.

### Pytest-cov

Plugin do Pytest integrado ao `coverage.py` para medir a cobertura de código pelos testes e gerar relatórios em terminal e HTML.

### httpx2

Client HTTP assíncrono utilizado pelo `TestClient` do FastAPI/Starlette para execução dos testes de endpoints da API.

### Taskipy

Task runner para Python que permite criar atalhos padronizados para comandos utilizados frequentemente no projeto, como execução de linters, testes e servidor.
