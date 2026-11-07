# Eleição de líder via Lease do Kubernetes no jobs_worker — Design

**Data:** 2026-11-07
**Issue:** #273 — feat(coordenação): eleição de líder via Lease do Kubernetes no jobs_worker (Entrega 3)
**Status:** aguardando aprovação

## 1. Intenção e porquê

O `jobs_worker` roda, em toda réplica, os loops singleton `outbox-relay` e
`job-reaper` (`linx_core/services/jobs_worker/src/jobs_worker/main.py`). Com 2+
réplicas há trabalho de coordenação duplicado. Esta feature faz com que apenas
uma réplica (o **líder**) execute esses loops, usando `coordination.k8s.io/v1
Lease` como mecanismo nativo de eleição. O consumo de filas (`run_consumer`)
continua em todas as réplicas.

A issue #273 já fixa o design (Lease, identity = pod name, duração 15s, config
por env). Este documento registra as três decisões abertas que foram tomadas
com o usuário antes do plano.

## 2. Diagnóstico verificado

- `main.py` sobe threads: `outbox-relay`, `job-reaper`, `status-consumer` e N
  `provisioning-consumer-*`. Os dois primeiros são os loops singleton.
- `WorkerSettings` (`jobs_worker/config.py`) estende `Settings`
  (`linx_shared/core/config.py`, `extra="ignore"`). Env vars novas são
  absorvidas sem tocar nos demais serviços.
- `RabbitMQPublisher.__init__` **não** conecta eager (conecta em `publish()`);
  `run_consumer` já reconecta para sempre. Os bloqueadores fatais no startup
  são `_wait_for_dependencies()` (Postgres + RabbitMQ) e o `_declare_topology()`
  eager.
- Manifests k8s ficam em `infra/kubernetes/` (a issue cita `deploy/k8s`, que
  não existe). Base: `namespace`, `postgres`, `linx-config`, `agent-bridge`,
  `identity-api` + overlays (`dockerhub`, `ecr`).
- `linx_shared` **não** tem dependência `kubernetes` nem `requests`.
- Não existe workflow de publicação da imagem `jobs_worker` (só
  `identity-api`, `agent-bridge`, `tenant-app`).

## 3. Decisões (aprovadas pelo usuário)

| # | Decisão | Escolha |
| --- | --- | --- |
| D1 | Acesso à API do Kubernetes | **HTTP in-cluster com stdlib** (`urllib` + `ssl` + token do ServiceAccount). Zero dependência nova; fácil de fake nos testes. |
| D2 | Imagem do `jobs_worker` | **Adicionar `publish-jobs-worker-image.yml`** reusando `publish-linx-core-image.yml`, imagem `includeluisferreira/jobs-worker:dev`. |
| D3 | Demo sem RabbitMQ no cluster | **Eleição independente do RabbitMQ**: o eleitor sobe em thread própria antes de `_wait_for_dependencies()`; os loops singleton só iniciam após dependências prontas + liderança. |

## 4. Abordagens consideradas

### Acesso ao k8s (D1)

- **A — HTTP in-cluster (stdlib), escolhida.** `urllib.request` com `SSLContext`
  carregando o CA de `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`,
  token de `.../token`, base URL de `KUBERNETES_SERVICE_HOST/PORT`. Sem
  dependência nova; client fica atrás de um `LeaseClient` (Protocol) fakeável.
  Custo: ~60–80 linhas de TLS/JSON próprias.
- **B — lib oficial `kubernetes`.** `CoordinationV1Api` cuida de token/CA e
  optimistic concurrency. Mais robusto, porém adiciona dependência pesada ao
  `linx_shared`, compartilhado por todos os serviços.

### Imagem (D2)

- **A — publish workflow, escolhida.** Reusa o workflow reutilizável já
  existente. Reproduzível via CI. Expande escopo em 1 arquivo de workflow.
- **B — build/push manual.** Mantém escopo estrito, mas o deploy não é
  reproduzível via CI.

### Demo sem RabbitMQ (D3)

- **A — eleição independente, escolhida.** O eleitor inicia imediatamente (thread
  própria) e a eleição é observável (`kubectl get lease`, logs `acquired`)
  mesmo sem broker. Os loops singleton aguardam dependências prontas + liderança.
- **B — RabbitMQ externo.** Preserva o startup atual; depende de um broker
  alcançável no ambiente do demo.

## 5. Arquitetura proposta

### 5.1 `linx_shared/coordination/leader.py` (novo)

- `LeaseClient` (Protocol): `get`, `create`, `replace` — retornam `dict | None`
  e levantam `LeaseNotFoundError` (404) / `LeaseConflictError` (409).
- `InClusterLeaseClient`: implementação HTTP (D1) do protocolo.
- `resolve_identity(env_identity) -> str`: `LEADER_ELECTION_IDENTITY` → `HOSTNAME`
  → `uuid4`.
- `K8sLeaderElector`: interface `run(stop_event)`; callbacks `on_started_leading`
  / `on_stopped_leading`. Adquire cria o Lease; renova atualizando `renewTime`
  com optimistic concurrency; perde liderança em conflito (409) ou holder
  estrangeiro não expirado. Logs `leader election: acquired` / `renewed` / `lost`.
  Clock injetável (`clock: Callable[[], datetime]`) para testes determinísticos.

### 5.2 Integração no `jobs_worker`

- `WorkerSettings` ganha: `leader_election_enabled: bool = False`,
  `leader_election_lease_name: str = "jobs-worker"`,
  `leader_election_namespace: str = "linx"`,
  `leader_election_identity: str = ""`,
  `leader_election_lease_duration_seconds: int = 15`.
- `run_outbox_relay(...)` e `JobReaper.run_forever(...)` ganham parâmetros
  opcionais `leader_event` (e, no caso do relay, `ready_event`). Quando ausentes,
  comportamento atual é preservado (compatibilidade Compose/testes).
- Em `main()`, quando `leader_election_enabled`: eleitor sobe primeiro; readiness
  de dependências vira não-fatal (thread de fundo com `ready_event`); os loops
  singleton aguardam `ready_event` + `leader_event`.

### 5.3 Manifests k8s

- `infra/kubernetes/base/jobs-worker.yaml`: `Deployment` (replicas 3),
  `ServiceAccount` `jobs-worker`, `Role`/`RoleBinding` com `get/create/update/
  patch` em `coordination.k8s.io` `leases` no namespace `linx`.
- `linx-config.yaml`: variáveis `LEADER_ELECTION_*` (não-secretas).
- `linx-secrets.example.env`: chave `RABBITMQ_AMQP_URL`.
- `kustomization.yaml` base + `k8s-ci.yml` + `README.md` atualizados.

## 6. Fora de escopo

Reescrever lock de migrations/lease de jobs (só documentar); Redis/Lamport
(#258); eleição para outros serviços; eleição em Compose; RabbitMQ no cluster.

## 7. O que fica para o plano

Quebra em tarefas TDD com testes antes da implementação, validação de manifesto
com `kubectl kustomize`/`--dry-run=client`, e ordem de commits. Nenhum commit
será feito sem autorização explícita do usuário.
