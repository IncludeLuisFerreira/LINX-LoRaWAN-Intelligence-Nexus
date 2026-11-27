# Jobs Status Worker — Design

**Data:** 2026-11-26
**Issue:** #232
**Status:** Aprovado (abordagem A)

## Intenção

Separar o consumo de eventos de status do `jobs_worker` em um processo/serviço
próprio (`jobs_status_worker`), como descrito em
`docs/superpowers/specs/2026-10-24-async-jobs-platform-design.md` (linhas 21,
56 e 284). Hoje o `StatusProcessor` roda como thread dentro do `jobs_worker`;
uma falha ou restart do worker de domínio derruba também a aplicação de
status. A separação permite ciclo de vida, escala e imagem independentes.

## Por que agora

Follow-up explícito de #58 / PR #231: o caminho event-sourced lógico já existe
e é idempotente; falta apenas o isolamento de processo. Adiar mantém a
promessa da spec quebrada e acopla a disponibilidade da consulta de jobs ao
provisionamento.

## Objetivos

- Criar `linx_core/services/jobs_status_worker/` como serviço Python autônomo,
  com `pyproject.toml`, `Dockerfile` e testes próprios.
- Consumir exclusivamente `linx.jobs.status` e aplicar eventos via
  `StatusProcessor` / `apply_status_event`.
- Remover o `status-consumer` e o `StatusProcessor` do `jobs_worker`.
- Entregar o deploy completo: compose de desenvolvimento, manifestos
  Kubernetes, workflow de publicação de imagem e matriz de CI.
- Manter o contrato de mensagens (`JobStatusEvent`), a fila e a idempotência
  existentes.

## Não-objetivos

- Mudar o formato de `JobStatusEvent` ou a topologia RabbitMQ.
- Alterar `apply_status_event` ou a máquina de estados.
- Criar banco, exchange ou fila novas.
- Introduzir leader election no status worker.
- Refatorar o `jobs_worker` além do necessário para remover o status.
- Migrar `docker_provisioner` ou o `identity_api`.

## Anti-objetivos

- Dois consumidores de status permanentes no mesmo ambiente (old + new) sem
  remoção do antigo.
- Duplicar o loop AMQP em dois pacotes de serviço.
- Fazer o status worker exigir `SERVICE_TOKEN` ou `PROVISIONER_GRPC_HOST`.
- Quebrar rolling deploy: durante a transição, eventos duplicados entre
  consumidores antigos e novos devem ser seguros (já são, por idempotência).

## Restrições

- Python `>=3.12,<4.0`; Poetry `2.4.1`; `black`/`isort` com linha 79;
  `flake8` e `mypy` limpos; cobertura de CI `>=70%`.
- Commits em português, Conventional Commits, referenciando `(#232)`.
- Uma branch por issue: `feat/jobs-status-worker`.
- `git add` explícito por arquivo; nada de `git add .`.
- Sem segredos reais em código, compose ou manifestos.

## Abordagens consideradas

### A — Serviço novo isolado (escolhida)

Novo pacote `jobs_status_worker`, imagem `jobs-status-worker`, Dockerfile e
workflow próprios. `run_consumer` sobe para `linx_shared.jobs.consumer` para
evitar duplicação.

- Prós: entrega o isolamento pedido; imagem mínima (sem gRPC/provisioner);
  configuração mínima; deploy e escala independentes; alinhado à spec.
- Contras: mais arquivos; exige extração do consumidor para `shared`.

### B — Segundo entrypoint no mesmo pacote/imagem

`python -m jobs_worker.status_main`, segundo Deployment com `command`
diferente.

- Prós: menos boilerplate; um artefato.
- Contras: imagem carrega gRPC/provisioner; config precisa ser fatiada mesmo
  assim; não atende ao pedido de Dockerfile próprio; mudanças no worker de
  domínio forçam redeploy do status worker.

### C — Serviço novo reusando a imagem do `jobs_worker`

Meio-termo, mas mantém a imagem acoplada e ainda exige separar settings. Sem
vantagem relevante sobre A.

**Decisão:** A.

## Decisões de implementação

### Pacote e módulos

```text
linx_core/services/jobs_status_worker/
├── Dockerfile
├── pyproject.toml
├── poetry.lock
├── src/jobs_status_worker/
│   ├── __init__.py
│   ├── config.py      # StatusWorkerSettings
│   ├── health.py      # Postgres + RabbitMQ
│   ├── main.py        # boot, consumidores, shutdown
│   └── status.py      # StatusProcessor (movido do jobs_worker)
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_main.py
    ├── test_startup_config.py
    └── test_status_processor.py
```

### Configuração

`StatusWorkerSettings` herda `linx_shared.core.config.Settings` e valida:

- `RABBITMQ_AMQP_URL` obrigatório, rejeitando `guest:guest`;
- `STATUS_QUEUE` padrão `linx.jobs.status` (`PROVISIONING_STATUS_QUEUE`),
  não vazio;
- `STATUS_CONCURRENCY` padrão `2`, positivo;
- `STATUS_PREFETCH` padrão `4`, positivo.

Não valida `SERVICE_TOKEN` nem `PROVISIONER_GRPC_HOST`; ambos continuam
disponíveis na base com default vazio, mas não são exigidos.

### Execução

`main.py`:

1. Configura logging e carrega `StatusWorkerSettings`.
2. Aguarda Postgres (`SELECT 1 FROM jobs LIMIT 1`) e RabbitMQ, com retry.
3. Declara a topologia (`declare_topology(channel, status_queue)`).
4. Sobe `STATUS_CONCURRENCY` threads `run_consumer` na `status_queue`, com
   `STATUS_PREFETCH`, ack após commit e nack sem requeue para mensagem
   inválida.
5. Encerra em `SIGTERM`/`SIGINT`, com `join(timeout=5)`.

Sem outbox relay, sem reaper e sem leader election: o status consumer pode
escalar horizontalmente porque `apply_status_event` é idempotente e protege
estados terminais.

### Extração do consumidor AMQP

Mover `InvalidMessageError`, `run_consumer` e `RECONNECT_DELAY_SECONDS` para
`linx_core/shared/src/linx_shared/jobs/consumer.py`, preservando assinatura:

```python
def run_consumer(
    queue: str,
    callback: Callable[[bytes], None],
    url: str,
    prefetch: int,
    stop_event: threading.Event | None = None,
    *,
    declare: Callable[[Any], None] | None = None,
) -> None: ...
```

`jobs_worker.runtime` mantém apenas outbox relay e registry; `jobs_worker.main`
passa a importar o consumidor de `linx_shared.jobs.consumer`. Os testes do loop
migram para `linx_core/shared/tests/test_job_consumer.py`.

### Remoção no `jobs_worker`

- Remover `status_consumer`, `status_callback`, `_parse_status_event`,
  `StatusProcessor` e o import de `PROVISIONING_STATUS_QUEUE` do `main.py`.
- Deletar `jobs_worker/status.py` e `tests/test_status_processor.py`.
- Manter os testes de envelope e de outbox intactos.
- Durante a janela de rolling deploy, `jobs_worker` antigo e
  `jobs_status_worker` novo podem consumir a mesma fila; eventos duplicados
  são absorvidos por `apply_status_event`.

### Deploy

- **Compose dev** (`linx_core/docker-compose.yml`): serviço
  `jobs_status_worker`, build a partir do novo Dockerfile, `depends_on` db e
  rabbitmq saudáveis, healthcheck próprio.
- **Kubernetes** (`infra/kubernetes/base/jobs-status-worker.yaml`):
  Deployment com 2 réplicas, `initContainer` `wait-for-db`, `envFrom`
  `linx-config` + `linx-secrets`. Sem ServiceAccount, Role, Service ou Lease.
  Adicionar ao `kustomization.yaml` e ao overlay ECR.
- **Publicação**: `.github/workflows/publish-jobs-status-worker-image.yml`,
  imagem `includeluisferreira/jobs-status-worker`, paths do serviço e de
  `linx_core/shared/**`.
- **CI**: adicionar `services/jobs_status_worker` às matrizes de lint e test e
  ao bloco de instalação do `backend-ci.yml`; adicionar assert do novo
  Deployment no `k8s-ci.yml`.
- **Docs**: `linx_core/README.md` (passo 5 deixa de dizer "o mesmo worker") e
  `infra/kubernetes/README.md` (tabela de imagens, contagem de pods, mapa de
  paths → serviço/workflow).

## Validação

Obrigatória por task: `black --check`, `isort --check-only`, `flake8`, `mypy`
e `pytest` nos pacotes `shared`, `services/jobs_worker` e
`services/jobs_status_worker`. Validação de render:
`kubectl kustomize infra/kubernetes` e overlay `ecr`.

Smoke manual de isolamento:

1. Subir `db`, `rabbitmq`, `identity_api`, `jobs_worker` e
   `jobs_status_worker` via compose.
2. Criar aplicação/provisionamento; confirmar `202`, consumo pelo
   `jobs_worker`, evento em `linx.jobs.status` e status final aplicado pelo
   `jobs_status_worker` (logs dos dois containers).
3. Parar o `jobs_worker` e publicar um `JobStatusEvent` válido na fila de
   status; confirmar que o `jobs_status_worker` aplica e faz ack mesmo sem o
   worker de domínio.
4. Reiniciar o `jobs_worker` e confirmar que ele não consome mais
   `linx.jobs.status` (nenhum log de status).

## O que fica para o builder

- Nomes exatos de funções e assinaturas estão no plano de implementação.
- Detalhes de formatação de manifests seguem o padrão do
  `infra/kubernetes/base/jobs-worker.yaml`.
- Qualquer necessidade de mudança fora dos arquivos listados deve ser
  interrompida e reportada, conforme `AGENTS.md`.
