# Fatia 1 — Broker único no stack base (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar um único RabbitMQ, definido em `infra/docker-compose.base.yml`, compartilhado por `linx_core`, `client` e testes, com credenciais canônicas e guardas de CI contra regressão.

**Architecture:** O broker passa a viver no stack base, na rede externa `linx-network` (nome parametrizável por `LINX_NETWORK`). `linx_core` deixa de ter broker próprio e consome o serviço externo; o stack `deploy` foi removido. A suíte de integração sobe os serviços reais em uma montagem própria, em rede/projeto isolados. Um verificador estático garante que nenhuma outra definição de RabbitMQ reapareça.

**Tech Stack:** Docker Compose v2, Python 3.12 (stdlib), GitHub Actions, Bash/Make.

**Spec:** `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`

## Status de execução (2026-11-27)

Este plano foi ajustado durante a execução:

- O stack `deploy/` foi removido por decisão de produto (commit `22833cf`).
- Task 3 virou "remover o stack deploy e limpar Makefile/README", não "deploy sem broker".
- Task 4 usa `tests/integration/telemetry/docker-compose.stack.yml`, com `routing` e `telemetry_consumer` construídos dos Dockerfiles reais; as portas vêm de `test.env`, sem `!override`.
- Task 5 cria `.github/workflows/messaging-ci.yml` e `scripts/requirements-tools.txt`.
- Commits da fatia: `3503302` (broker + checker), `c478ccb` (integração), `d64b128` (portas por env), `22833cf` (remoção do deploy).

## Global Constraints

- Exatamente **uma** definição de serviço `rabbitmq` nos compose de aplicação, em `infra/docker-compose.base.yml`.
- Nome da rede parametrizável: `name: ${LINX_NETWORK:-linx-network}`, sempre `external: true` fora do base.
- Credenciais canônicas nos serviços: `RABBITMQ_ADMIN_USER` e `RABBITMQ_ADMIN_PASSWORD`. `RABBITMQ_DEFAULT_*` só pode aparecer **dentro** do serviço do broker, como mapeamento para as variáveis nativas do RabbitMQ.
- Portas do broker no base: `127.0.0.1:5672:5672` e `127.0.0.1:15672:15672`. Testes usam `5673`/`15673` via override.
- Imagem: `rabbitmq:3-management-alpine` (pinada por tag; sem `latest`).
- Python `>=3.12,<4.0`; sem dependências novas.
- Não tocar em `infra/kubernetes/**`, `proto/**`, `middleware/**` nem no domínio de jobs.
- AGENTS.md: uma branch por issue, `git add` explícito, commits em português com `(#N)`, sem tocar trabalho de outro agente.
- Branch de trabalho em worktree separado; o working tree principal está em `feat/jobs-status-worker` (#232).

## Review Focus

1. **Dois brokers com o mesmo alias DNS na rede** → serviço conecta no broker errado. Coberto por `scripts/check_messaging_topology.py` (definição única) e pelo isolamento de rede dos testes.
2. **Serviço sobe antes do broker ficar saudável** → worker fica ocioso sem erro claro. Coberto pela pré-checagem do Makefile e pelo smoke de health.
3. **Deriva de credencial (`DEFAULT` vs `ADMIN`)** → `ACCESS_REFUSED` em runtime. Coberto por checagem estática que proíbe `RABBITMQ_DEFAULT_` nos compose de aplicação.
4. **Teste de integração apontando para o broker de dev** → filas apagadas. Coberto por `LINX_NETWORK`/projeto isolados na suíte.
5. **Override referenciando serviço removido** → `docker compose config` inválido. Coberto pela validação de config de cada combinação compose+override.

---

### Task 0: Issue, worktree e docs

**Files:**
- Copy (do working tree principal para o worktree): `docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md`, `docs/superpowers/plans/2026-11-27-messaging-slice-1-single-broker.md`

**Interfaces:**
- Produces: branch `feat/f01-broker-unico`, worktree `../Linx-f01`, issue da fatia.

- [ ] **Step 1: Criar a issue da fatia**

```bash
cd /home/includeluisferreira/Documentos/projetos/reais/Linx
gh issue create \
  --title "feat(messaging): broker único no stack base (fatia 1)" \
  --body "Implementa a fatia 1 do design docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md: um RabbitMQ em infra/docker-compose.base.yml, remoção dos brokers duplicados de linx_core/deploy/testes, credenciais canônicas RABBITMQ_ADMIN_* e guarda de CI. Critério: make up-base/up-core/up-deploy usam o mesmo broker; check_messaging_topology passa."
```

Anote o número retornado; use `(#N)` nos commits.

- [ ] **Step 2: Criar worktree a partir de `develop` atualizado**

```bash
git fetch origin
git worktree add ../Linx-f01 -b feat/f01-broker-unico origin/develop
```

- [ ] **Step 3: Levar os documentos para o worktree**

```bash
cp docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md ../Linx-f01/docs/superpowers/specs/
cp docs/superpowers/plans/2026-11-27-messaging-slice-1-single-broker.md ../Linx-f01/docs/superpowers/plans/
cd ../Linx-f01
```

- [ ] **Step 4: Commitar os documentos**

```bash
git add docs/superpowers/specs/2026-11-27-messaging-consolidation-design.md docs/superpowers/plans/2026-11-27-messaging-slice-1-single-broker.md
git commit -m "docs(messaging): design e plano da fatia 1 (#N)"
```

---

### Task 1: Verificador estático + broker no stack base

**Files:**
- Create: `scripts/check_messaging_topology.py`
- Create: `scripts/__init__.py`
- Create: `scripts/tests/__init__.py`
- Create: `scripts/tests/test_check_messaging_topology.py`
- Modify: `infra/docker-compose.base.yml`
- Modify: `infra/.env.example`

**Interfaces:**
- Produces:
  - `rabbitmq_services(root: pathlib.Path) -> list[tuple[pathlib.Path, int]]`
  - `validate(root: pathlib.Path) -> list[str]` (lista de violações; vazia = ok)
  - `main(argv: list[str] | None = None) -> int` (0 ok, 1 violação; aceita `--root`)
- Consumes: nada.

- [ ] **Step 1: Escrever os testes do verificador (falhando)**

Criar `scripts/__init__.py` e `scripts/tests/__init__.py` vazios (necessários para `unittest discover -t .`).

`scripts/tests/test_check_messaging_topology.py`:

```python
import tempfile
import unittest
from pathlib import Path

from scripts.check_messaging_topology import validate


BASE_OK = """
services:
  rabbitmq:
    image: rabbitmq:3-management-alpine
networks:
  linx-network:
    external: true
    name: ${LINX_NETWORK:-linx-network}
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class ValidateTest(unittest.TestCase):
    def test_accepts_single_broker_in_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(root, "deploy/docker-compose.yml", "services:\n  db: {}\n")
            self.assertEqual(validate(root), [])

    def test_rejects_two_broker_definitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(
                root,
                "deploy/docker-compose.yml",
                "services:\n  rabbitmq:\n    image: rabbitmq:3-management\n",
            )
            self.assertTrue(any("rabbitmq" in v for v in validate(root)))

    def test_rejects_broker_outside_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root,
                "linx_core/docker-compose.yml",
                "services:\n  rabbitmq:\n    image: rabbitmq:3-management-alpine\n",
            )
            self.assertTrue(any("base" in v for v in validate(root)))

    def test_rejects_default_credentials_in_app_compose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "infra/docker-compose.base.yml", BASE_OK)
            _write(
                root,
                "deploy/docker-compose.yml",
                "services:\n  routing:\n    environment:\n"
                "      - RABBIT_URL=amqp://${RABBITMQ_DEFAULT_USER}:x@rabbitmq:5672/\n",
            )
            self.assertTrue(any("RABBITMQ_DEFAULT_" in v for v in validate(root)))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s scripts/tests -t . -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.check_messaging_topology'`.

- [ ] **Step 3: Implementar o verificador**

`scripts/check_messaging_topology.py` — responsabilidades:

- `COMPOSE_FILES` = todos os `docker-compose*.yml` sob `infra/`, `linx_core/`, `deploy/`, `client/` e `tests/`. Ignorar `node_modules` e `.venv`.
- `rabbitmq_services(root)` varre cada arquivo e retorna `(caminho, linha)` para linhas que casam `^\s*image:\s*rabbitmq:`.
- `validate(root)` retorna violações:
  1. quantidade de definições `image: rabbitmq:` != 1;
  2. a única definição não está em `infra/docker-compose.base.yml`;
  3. o base não declara `linx-network` com `external: true` e `name: ${LINX_NETWORK:-linx-network}`;
  4. qualquer compose fora do base contém `RABBITMQ_DEFAULT_`;
  5. qualquer bloco de serviço `rabbitmq:` **com `image:`** aparece em compose fora do base. Overrides que só ajustam `ports` (sem `image`) são permitidos.
- `main` imprime uma violação por linha em `stderr`, retorna 1; sem violações, imprime `ok` e retorna 0.

- [ ] **Step 4: Rodar os testes do verificador**

Run: `python3 -m unittest discover -s scripts/tests -t . -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Adicionar o broker ao stack base**

`infra/docker-compose.base.yml` ganha, antes de `volumes:`:

```yaml
  rabbitmq:
    image: rabbitmq:3-management-alpine
    restart: unless-stopped
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_ADMIN_USER:-linx}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_ADMIN_PASSWORD:?RABBITMQ_ADMIN_PASSWORD must be set}
    ports:
      - "127.0.0.1:5672:5672"
      - "127.0.0.1:15672:15672"
    volumes:
      - rabbitmqdata_base:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
    networks:
      - linx-network
```

E, no fim do arquivo:

```yaml
networks:
  linx-network:
    external: true
    name: ${LINX_NETWORK:-linx-network}

volumes:
  postgresqldata_base:
  redisdata_base:
  rabbitmqdata_base:
```

- [ ] **Step 6: Documentar credenciais no `infra/.env.example`**

Adicionar ao fim do arquivo:

```bash
# --- RabbitMQ do stack base (broker único) ---
# O compose lê este arquivo porque o projeto está em `infra/`.
# Os mesmos valores devem existir em `deploy/.env` e `linx_core/.env`,
# nas variáveis RABBITMQ_ADMIN_USER/RABBITMQ_ADMIN_PASSWORD.
RABBITMQ_ADMIN_USER=linx
RABBITMQ_ADMIN_PASSWORD=change-me-in-production
```

- [ ] **Step 7: Atualizar o bootstrap do `up-base`**

`Makefile`, target `up-base` passa a criar a rede antes:

```make
up-base:
	bash deploy/scripts/bootstrap-network.sh "$${LINX_NETWORK:-linx-network}"
	docker compose -f $(INFRA_BASE) up -d
```

- [ ] **Step 8: Validar o compose do base**

Run: `docker compose -f infra/docker-compose.base.yml config --quiet`
Expected: exit 0.

- [ ] **Step 9: Commit**

```bash
git add scripts/check_messaging_topology.py scripts/__init__.py scripts/tests/__init__.py scripts/tests/test_check_messaging_topology.py infra/docker-compose.base.yml infra/.env.example Makefile
git commit -m "feat(messaging): broker único no stack base (#N)"
```

---

### Task 2: `linx_core` sem broker próprio

**Files:**
- Modify: `linx_core/docker-compose.yml`
- Test: `scripts/tests/test_check_messaging_topology.py` (asserção de repositório)

**Interfaces:**
- Consumes: `validate` da Task 1.
- Produces: stack `linx_core` conectada ao broker externo.

- [ ] **Step 1: Escrever o teste de repositório (falhando)**

Adicionar em `scripts/tests/test_check_messaging_topology.py`:

```python
class RepositoryTest(unittest.TestCase):
    def test_repository_has_single_broker(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(validate(root), [])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s scripts/tests -t . -v`
Expected: FAIL listando `deploy` com broker próprio (o `linx_core` deixa de violar após a edição).

- [ ] **Step 3: Editar `linx_core/docker-compose.yml`**

- Remover o serviço `rabbitmq` (linhas 22-37) e o volume `rabbitmqdata`.
- Adicionar no fim:

```yaml
networks:
  linx-network:
    external: true
    name: ${LINX_NETWORK:-linx-network}
```

- Em `jobs_worker` e `jobs_status_worker`: adicionar `networks: [default, linx-network]` e remover `rabbitmq` do `depends_on`, mantendo `db` com `condition: service_healthy`.
- Em `identity_api`: adicionar `networks: [default, linx-network]` (usa management API quando provisiona tenant).
- Manter `RABBITMQ_AMQP_URL=...@rabbitmq:5672/` intacto.

- [ ] **Step 4: Validar o compose**

Run: `docker compose -f linx_core/docker-compose.yml config --quiet`
Expected: exit 0.

- [ ] **Step 5: Rodar os testes do verificador**

Run: `python3 -m unittest discover -s scripts/tests -t . -v`
Expected: FAIL apenas por causa de `deploy` (uma violação). A asserção de repositório só passa na Task 3.

- [ ] **Step 6: Commit**

```bash
git add linx_core/docker-compose.yml scripts/tests/test_check_messaging_topology.py
git commit -m "feat(messaging): linx_core usa o broker do stack base (#N)"
```

---

### Task 3: Remoção do stack deploy (superseded)

> **Execução real:** o `deploy/` foi removido por completo (commit `22833cf`).
> Os passos abaixo descrevem a versão original do plano ("deploy sem broker") e
> ficam como registro histórico. A limpeza de Makefile/README/docs está no
> commit seguinte da fatia.

**Files:**
- Modify: `deploy/docker-compose.yml`
- Modify: `deploy/.env.example`
- Test: `scripts/tests/test_check_messaging_topology.py`

**Interfaces:**
- Produces: `deploy` sem `rabbitmq`; `RABBIT_URL` e management usando `RABBITMQ_ADMIN_*`.
- Consumes: broker externo da Task 1.

- [ ] **Step 1: Estender o teste de repositório**

Adicionar:

```python
    def test_deploy_has_no_local_broker_and_uses_admin_creds(self):
        deploy = (Path(__file__).resolve().parents[2]
                  / "deploy" / "docker-compose.yml").read_text()
        self.assertNotIn("rabbitmq:\n    image:", deploy)
        self.assertNotIn("RABBITMQ_DEFAULT_", deploy)
        self.assertIn("RABBITMQ_ADMIN_USER", deploy)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s scripts/tests -t . -v`
Expected: FAIL nas asserções novas.

- [ ] **Step 3: Editar `deploy/docker-compose.yml`**

- Remover o serviço `rabbitmq` (linhas 148-166) e o volume `rabbitmq_data`.
- `telemetry_consumer`: remover `rabbitmq` do `depends_on`; adicionar `networks: [default, linx-network]`.
- `identity_api`: adicionar `networks: [default, linx-network]` (usa a management API do broker para provisionar tenant).
- `routing`: trocar o default de `RABBIT_URL` por

```yaml
      - RABBIT_URL=${RABBIT_URL:-amqp://${RABBITMQ_ADMIN_USER:-linx}:${RABBITMQ_ADMIN_PASSWORD:?RABBITMQ_ADMIN_PASSWORD must be set}@rabbitmq:5672/%2f}
```

- `identity_api` e `routing` já estão em `linx-network`; manter.
- Topo de `networks` passa a:

```yaml
networks:
  linx-network:
    external: true
    name: ${LINX_NETWORK:-linx-network}
```

- [ ] **Step 4: Atualizar `deploy/.env.example`**

- Remover `RABBITMQ_DEFAULT_USER` e `RABBITMQ_DEFAULT_PASS`.
- Manter `RABBITMQ_ADMIN_USER`/`RABBITMQ_ADMIN_PASSWORD`.
- Trocar o exemplo de `RABBIT_URL` para usar `RABBITMQ_ADMIN_USER`/`RABBITMQ_ADMIN_PASSWORD`.
- Remover a linha `RABBIT_EXCHANGE` (env fantasma) se existir.
- Atualizar o `.env` local (não versionado) de `deploy/` e `linx_core/` com os mesmos `RABBITMQ_ADMIN_USER`/`RABBITMQ_ADMIN_PASSWORD` definidos em `infra/.env`; sem isso o smoke da Task 6 falha com `ACCESS_REFUSED`.

- [ ] **Step 5: Validar compose e testes**

Run:
```
docker compose -f deploy/docker-compose.yml config --quiet
python3 -m unittest discover -s scripts/tests -t . -v
```
Expected: exit 0 e PASS em todos os testes, inclusive `test_repository_has_single_broker`.

- [ ] **Step 6: Commit**

```bash
git add deploy/docker-compose.yml deploy/.env.example scripts/tests/test_check_messaging_topology.py
git commit -m "feat(messaging): deploy usa o broker único e credenciais admin (#N)"
```

---

### Task 4: Suíte de integração isolada com montagem de teste (ajustada)

> **Execução real:** implementada com `tests/integration/telemetry/docker-compose.stack.yml`,
> construindo `routing` e `telemetry_consumer` dos Dockerfiles reais. As portas
> vêm de `test.env` (`RABBITMQ_AMQP_PORT` etc.); não há mais
> `docker-compose.override.yml`, `broker-override` nem `!override`.

**Files:**
- Modify: `tests/integration/telemetry/conftest.py`
- Modify: `tests/integration/telemetry/docker-compose.override.yml`
- Create: `tests/integration/telemetry/docker-compose.broker-override.yml`
- Modify: `tests/integration/telemetry/test.env`
- Test: `scripts/tests/test_check_messaging_topology.py`

**Interfaces:**
- Produces: `LINX_NETWORK=lynx-it-network`; broker iniciado por `infra/docker-compose.base.yml`; portas `5673/15673`.
- Consumes: definição única do broker.

- [ ] **Step 1: Escrever o teste de isolamento (falhando)**

Adicionar:

```python
    def test_integration_uses_base_broker_and_isolated_network(self):
        root = Path(__file__).resolve().parents[2]
        conftest = (root / "tests/integration/telemetry/conftest.py").read_text()
        self.assertIn("infra/docker-compose.base.yml", conftest)
        self.assertIn("lynx-it-network", conftest)
        override = (root / "tests/integration/telemetry/docker-compose.override.yml").read_text()
        self.assertNotIn("rabbitmq:", override)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest discover -s scripts/tests -t . -v`
Expected: FAIL nas asserções novas.

- [ ] **Step 3: Ajustar `conftest.py`**

- Adicionar `INFRA_BASE_COMPOSE = os.path.join(ROOT, "infra", "docker-compose.base.yml")`.
- Definir `NETWORK = os.environ.get("LINX_NETWORK", "lynx-it-network")`.
- `SERVICES` passa a `("timescaledb", "telemetry_consumer", "routing")`.
- `_ensure_network()` chama o bootstrap com `NETWORK` e exporta `LINX_NETWORK` no ambiente dos subprocessos de compose.
- `compose()` inclui `-f INFRA_BASE_COMPOSE` antes de `BASE_COMPOSE` (deploy) e do override.
- O `up` sobe `rabbitmq` a partir do base junto com `*SERVICES`.
- AMQP/MGMT passam a ler `RABBITMQ_ADMIN_USER`/`RABBITMQ_ADMIN_PASSWORD` do `test.env`.
- `_dump_logs` continua com `rabbitmq`.

- [ ] **Step 4: Ajustar overrides e `test.env`**

- `docker-compose.override.yml`: remover o bloco `rabbitmq:` inteiro.
- Criar `docker-compose.broker-override.yml` apenas com:

```yaml
services:
  rabbitmq:
    ports: !override
      - "127.0.0.1:5673:5672"
      - "127.0.0.1:15673:15672"
```

- `test.env`: remover `RABBITMQ_DEFAULT_USER/PASS`; manter `RABBITMQ_ADMIN_*`; garantir `LINX_NETWORK=lynx-it-network`.

- [ ] **Step 5: Validar configuração combinada**

Run:
```
LINX_NETWORK=lynx-it-network docker compose -p lynx-integration-check \
  --env-file tests/integration/telemetry/test.env \
  -f infra/docker-compose.base.yml \
  -f deploy/docker-compose.yml \
  -f tests/integration/telemetry/docker-compose.override.yml \
  -f tests/integration/telemetry/docker-compose.broker-override.yml \
  config --quiet
```
Expected: exit 0.

- [ ] **Step 6: Rodar a suíte de integração (Docker local)**

Run: `tests/integration/run.sh -k isolation`
Expected: PASS; ao final, nenhum container do projeto de teste permanece, e o broker de dev (se estava no ar) continua intocado.

- [ ] **Step 7: Commit**

```bash
git add tests/integration/telemetry/conftest.py tests/integration/telemetry/docker-compose.override.yml tests/integration/telemetry/docker-compose.broker-override.yml tests/integration/telemetry/test.env scripts/tests/test_check_messaging_topology.py
git commit -m "test(messaging): integração usa o broker do base em rede isolada (#N)"
```

---

### Task 5: Guardas de CI, Makefile e documentação (ajustada)

> **Execução real:** `.github/workflows/messaging-ci.yml` instala
> `scripts/requirements-tools.txt` (PyYAML) e roda o checker + testes. O
> Makefile perdeu `up-deploy`/`up-client-agent`; `up-core`/`up-client` assumem
> o broker do `up-base`. README e docs vivos foram atualizados.

**Files:**
- Create: `.github/workflows/messaging-ci.yml`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `linx_core/README.md` (seção de stacks/arquitetura)

**Interfaces:**
- Consumes: `scripts/check_messaging_topology.py`.
- Produces: `make check-messaging`; CI que roda o verificador e os unit tests.

- [ ] **Step 1: Adicionar target e pré-checagem no Makefile**

Adicionar `check-messaging` e `require-broker`, e **substituir** os targets `up-core` e `up-deploy` existentes (não duplicar a definição):

```make
check-messaging:
	python3 scripts/check_messaging_topology.py --root .

require-broker:
	@docker compose -f $(INFRA_BASE) ps rabbitmq --status running 2>/dev/null | grep -q rabbitmq \
	  || { echo "broker ausente: rode 'make up-base' antes"; exit 1; }

up-core: require-broker
	docker compose -f $(CORE) up -d

up-deploy: require-broker
	bash deploy/scripts/bootstrap-network.sh "$${LINX_NETWORK:-linx-network}"
	docker compose -f $(DEPLOY) up -d
```

- [ ] **Step 2: Criar o workflow**

`.github/workflows/messaging-ci.yml`:

```yaml
name: messaging-ci
on:
  pull_request:
    paths:
      - "infra/docker-compose*.yml"
      - "linx_core/docker-compose*.yml"
      - "deploy/docker-compose*.yml"
      - "client/docker-compose*.yml"
      - "tests/integration/**/docker-compose*.yml"
      - "scripts/check_messaging_topology.py"
      - "scripts/tests/**"
      - ".github/workflows/messaging-ci.yml"
  push:
    branches: [main, develop]
    paths:
      - "infra/docker-compose*.yml"
      - "linx_core/docker-compose*.yml"
      - "deploy/docker-compose*.yml"
      - "scripts/check_messaging_topology.py"
      - ".github/workflows/messaging-ci.yml"
jobs:
  topology:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python3 scripts/check_messaging_topology.py --root .
      - run: python3 -m unittest discover -s scripts/tests -t . -v
```

- [ ] **Step 3: Atualizar README**

Na tabela de stacks (linhas 71-80):
- `make up-base` passa a listar "PostgreSQL + Redis + Mosquitto + RabbitMQ".
- Adicionar nota: `up-core` e `up-deploy` exigem `make up-base` no ar; o broker é único e compartilhado.
- Remover a menção de broker próprio do `deploy`.

Em `linx_core/README.md`, atualizar a seção de ambiente: o broker vem do stack base, não do compose de `linx_core`.

- [ ] **Step 4: Validar localmente**

Run:
```
python3 scripts/check_messaging_topology.py --root .
python3 -m unittest discover -s scripts/tests -t . -v
make check-messaging
```
Expected: `ok` e PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/messaging-ci.yml Makefile README.md linx_core/README.md
git commit -m "ci(messaging): guarda broker único e documenta a stack base (#N)"
```

---

### Task 6: Validação final da fatia

**Files:** nenhum (somente verificação).

- [ ] **Step 1: Validação estática**

Run:
```
python3 scripts/check_messaging_topology.py --root .
docker compose -f infra/docker-compose.base.yml config --quiet
docker compose -f linx_core/docker-compose.yml config --quiet
```
Expected: todos exit 0; o verificador imprime `ok`.

- [ ] **Step 2: Smoke de dev**

Run:
```
make up-base
make up-core
docker ps --format '{{.Image}}' | grep -c '^rabbitmq:3-management-alpine$'
```
Expected: `1`. Os serviços de `linx_core` sobem com health `healthy` (ou `starting` no primeiro minuto).

- [ ] **Step 3: Smoke do client**

Run:
```
make up-client
docker ps --format '{{.Image}}' | grep -c '^rabbitmq:3-management-alpine$'
```
Expected: `1` (o mesmo container). `telemetry_consumer` alcança `rabbitmq:5672`.

- [ ] **Step 4: Derrubar e confirmar limpeza**

Run:
```
make down-deploy
make down-core
make down-base
```
Expected: containers param. Os volumes antigos `linx_core_rabbitmqdata` e `deploy_rabbitmq_data` ficam órfãos (dados do broker antigo). **Não** apague automaticamente: registre na issue que a limpeza é manual e opcional, conforme o cutover pré-lançamento decidido no design.

- [ ] **Step 5: Rodar a suíte de integração completa**

Run: `tests/integration/run.sh`
Expected: PASS, inclusive os testes de isolamento multi-tenant.

- [ ] **Step 6: Registrar o resultado na issue**

Comente na issue da fatia (`gh issue comment N --body "..."` ou texto equivalente) com: comandos executados, saída do verificador, contagem de containers `rabbitmq` e resultado da suíte de integração. Não abra PR sem essa evidência.

---

## Self-review do plano

- **Cobertura do design (fatia 1):** broker no base (Task 1), remoção em linx_core (2), remoção em deploy + credenciais (3), testes isolados (4), guardas/CI/docs (5), validação (6). Gate de go-live e itens de produto ficam registrados no design como follow-up, fora desta fatia.
- **Fora do escopo desta fatia, deliberadamente:** `linx_shared.messaging`, topologia declarativa (#233), política de DLQ/retry (#234), migração Pika, telemetria na topologia comum, observabilidade. Cada um tem fatia própria no design.
- **Consistência de tipos:** `validate(root) -> list[str]` é usada nas Tasks 1-5; `rabbitmq_services` é interna ao script; nomes de rede (`LINX_NETWORK`, `lynx-it-network`) e credenciais (`RABBITMQ_ADMIN_*`) são idênticos em todas as tasks.
- **Review Focus:** cada um dos 5 modos de falha tem teste na task que o introduz.
