# Eleição de líder via Lease do Kubernetes no jobs_worker — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer com que, com N réplicas do `jobs_worker`, exatamente 1 execute `outbox-relay` e `job-reaper`, usando `coordination.k8s.io/v1 Lease`.

**Architecture:** Um `K8sLeaderElector` (em `linx_shared/coordination/leader.py`) disputa um `Lease` via HTTP in-cluster (stdlib, token do ServiceAccount). No `jobs_worker`, o eleitor sobe em thread própria e alterna um `threading.Event` de liderança; `outbox-relay` e `job-reaper` passam a condicionar sua execução a esse evento (e a um evento de readiness). Com `LEADER_ELECTION_ENABLED=false`, o comportamento atual é preservado.

**Tech Stack:** Python 3.12, stdlib (`urllib`/`ssl`/`json`/`threading`), pydantic-settings, Kubernetes `Lease` (`coordination.k8s.io/v1`), Kustomize, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-07-leader-election-jobs-worker-design.md` (decisões D1–D3) + issue #273.

## Global Constraints

- Python `>=3.12,<4.0`; código em `linx_core/` (FastAPI/gRPC) e manifests em `infra/kubernetes/`.
- `black`/`isort` line-length 79; `mypy src/ tests/` e `flake8 src/ tests/` devem passar em `linx_core/shared` e `linx_core/services/jobs_worker`.
- Commits em **português**, Conventional Commits, referenciando `(#273)`.
- `git add` explícito, arquivo por arquivo; nunca `git add .`/`-A`/`commit -a`.
- Testes: `env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest` e `env -u VIRTUAL_ENV poetry -C shared run pytest` (exigem Postgres em `127.0.0.1:5432`; RabbitMQ é fake nos testes).
- Manifests validados por `kubectl kustomize infra/kubernetes` (CI `k8s-ci.yml`).
- Escopo estrito da issue #273 (AGENTS.md): não mexer em `docs/superpowers/plans/2026-11-07-k3s-terraform-apply-kubectl-deploy.md`, `docs/superpowers/specs/2026-11-07-k3s-terraform-apply-kubectl-deploy-design.md` nem em arquivos de outras issues.

## Review Focus

1. **Renovação atrasada não pode criar dois líderes.** Se um líder não consegue renovar dentro do `leaseDurationSeconds`, ele deve largar a liderança (`on_stopped_leading`) antes de o Lease expirar; senão dois pods processam outbox/reaper juntos. → Task 2, `test_loses_leadership_when_renew_fails_past_deadline`.
2. **Renovação obsoleta não pode sobrescrever o novo titular.** Um `replace` com `resourceVersion` defasado (409) não deve gravar por cima do holder atual. → Task 2, `test_stale_renew_does_not_clobber_holder` + Task 1, `test_replace_maps_409_to_conflict`.
3. **Identity única por pod.** Dois pods com `HOSTNAME` vazio colidiriam no mesmo holder; o fallback `uuid4` evita. → Task 1, `test_resolve_identity_prefers_env_then_hostname_then_uuid`.
4. **Flag desligada preserva o startup atual.** Com `LEADER_ELECTION_ENABLED=false`, os parâmetros de gating ausentes não podem alterar `outbox-relay`/`reaper`/`main`. → Task 3 (parâmetros default `None`) + Task 4, `test_worker_settings_leader_election_defaults`.
5. **Lease removido externamente não pode travar o eleitor.** Se o Lease for deletado enquanto se lidera, o eleitor deve re-adquirir (recriar) em vez de crashar. → Task 2, `test_lease_deleted_externally_triggers_reacquire`.

---

### Task 1: Cliente HTTP do Lease + `resolve_identity`

**Files:**
- Create: `linx_core/shared/src/linx_shared/coordination/__init__.py`
- Create: `linx_core/shared/src/linx_shared/coordination/leader.py`
- Test: `linx_core/shared/tests/test_leader_election_http.py`

**Interfaces:**
- Produces:
  - `class LeaderElectionError(Exception)`; `class LeaseNotFoundError(LeaderElectionError)`; `class LeaseConflictError(LeaderElectionError)`.
  - `class LeaseClient(Protocol)` com `get(namespace: str, name: str) -> dict[str, Any] | None`, `create(namespace: str, name: str, body: dict[str, Any]) -> dict[str, Any]`, `replace(namespace: str, name: str, body: dict[str, Any]) -> dict[str, Any]`. `get` retorna `None` em 404; `create`/`replace` levantam `LeaseConflictError` em 409 e `LeaderElectionError` em outros erros HTTP.
  - `class InClusterLeaseClient` com `__init__(self, *, base_url: str | None = None, token: str | None = None, ca_cert: str | None = None, timeout: float = 5.0)`. `base_url` default `https://{KUBERNETES_SERVICE_HOST}:{KUBERNETES_SERVICE_PORT}`; `token` default do arquivo `/var/run/secrets/kubernetes.io/serviceaccount/token`; `ca_cert` default de `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`. Caminho da API: `/apis/coordination.k8s.io/v1/namespaces/{ns}/leases/{name}`.
  - `def resolve_identity(env_identity: str | None = None) -> str`: `env_identity` (não vazio) → `os.environ["HOSTNAME"]` → `str(uuid4())`.

- [ ] **Step 1: Escrever os testes que falham**

`linx_core/shared/tests/test_leader_election_http.py` usa `monkeypatch` em `linx_shared.coordination.leader.urllib.request.urlopen` (fake que grava `Request` e devolve resposta; para erro, levanta `urllib.error.HTTPError`).

```python
def test_get_maps_to_get_request(monkeypatch):
    # client.get("linx", "jobs-worker") chama urlopen com método GET,
    # URL ".../apis/coordination.k8s.io/v1/namespaces/linx/leases/jobs-worker",
    # header Authorization: Bearer <token>, e devolve o dict parseado.

def test_get_returns_none_on_404(monkeypatch):
    # urlopen levanta HTTPError(code=404) -> client.get(...) is None

def test_create_posts_body(monkeypatch):
    # método POST, corpo JSON == body, devolve o dict criado

def test_replace_puts_body(monkeypatch):
    # método PUT, corpo JSON == body

def test_replace_maps_409_to_conflict(monkeypatch):
    # HTTPError(409) -> pytest.raises(LeaseConflictError)

def test_other_http_errors_raise_leader_election_error(monkeypatch):
    # HTTPError(500) -> pytest.raises(LeaderElectionError)

def test_resolve_identity_prefers_env_then_hostname_then_uuid(monkeypatch):
    # resolve_identity("pod-0") == "pod-0"
    # resolve_identity("") + HOSTNAME="pod-1" == "pod-1"
    # resolve_identity("") + sem HOSTNAME -> str parseable como UUID
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_leader_election_http.py -v`
Expected: FAIL (ImportError: `linx_shared.coordination` inexistente).

- [ ] **Step 3: Implementar `leader.py` (client + exceptions + identity)**

`InClusterLeaseClient._request(method, namespace, name, body) -> dict | None` usa `urllib.request.Request` com `method`, `data=json.dumps(body)` (quando houver), header `Authorization: Bearer {token}` e `Content-Type: application/json`; `urlopen` com `context=ssl.create_default_context(cafile=ca_cert)`; mapeia `HTTPError` 404 → `None`, 409 → `LeaseConflictError`, demais → `LeaderElectionError`.

- [ ] **Step 4: Rodar e confirmar passagem**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_leader_election_http.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add linx_core/shared/src/linx_shared/coordination/__init__.py \
        linx_core/shared/src/linx_shared/coordination/leader.py \
        linx_core/shared/tests/test_leader_election_http.py
git commit -m "feat(coordenação): adiciona cliente HTTP in-cluster de Lease (#273)"
```

---

### Task 2: `K8sLeaderElector` (adquirir / renovar / perder / readquirir)

**Files:**
- Modify: `linx_core/shared/src/linx_shared/coordination/leader.py`
- Test: `linx_core/shared/tests/test_leader_election.py`

**Interfaces:**
- Consumes: `LeaseClient`, `LeaseConflictError`, `LeaseNotFoundError` (Task 1).
- Produces:
  - `class K8sLeaderElector` com `__init__(self, *, client: LeaseClient, identity: str, namespace: str = "linx", lease_name: str = "jobs-worker", lease_duration_seconds: int = 15, renew_deadline_seconds: int = 10, retry_period_seconds: float = 2.0, clock: Callable[[], datetime] | None = None, on_started_leading: Callable[[], None] | None = None, on_stopped_leading: Callable[[], None] | None = None)`. `clock` default `lambda: datetime.now(timezone.utc)`.
  - `run(self, stop_event: threading.Event) -> None` (loop bloqueante).
  - Corpo do Lease: `{"apiVersion": "coordination.k8s.io/v1", "kind": "Lease", "metadata": {"name", "namespace", "resourceVersion"}, "spec": {"holderIdentity", "leaseDurationSeconds", "acquireTime", "renewTime"}}`; tempos em ISO 8601 UTC via `clock().isoformat(timespec="microseconds")`.

Algoritmo `run` (pin de comportamento; o corpo exato é do implementador):

```text
leading = False
while not stop_event.is_set():
    if not leading:
        if _try_acquire():            # ver _try_acquire abaixo
            leading = True
            on_started_leading() if set
        else:
            stop_event.wait(retry_period); continue
    # fase de renovação
    while leading and not stop_event.is_set():
        stop_event.wait(retry_period)
        if stop_event.is_set(): break
        if not _try_renew():          # ver _try_renew abaixo
            leading = False
    if just lost leadership:
        on_stopped_leading() if set

_try_acquire():
    lease = client.get(ns, name)
    if lease is None:
        client.create(ns, name, body{holder=identity, renewTime=now,
                                     acquireTime=now, duration=d})   # True; 409 -> False
        return True
    expired = parse(renewTime) + d <= now
    if holder == identity or expired:
        client.replace(ns, name, body{holder=identity, renewTime=now,
                                      acquireTime=lease.spec.acquireTime ou now,
                                      resourceVersion=lease.metadata.resourceVersion})
        return True                    # 409/404 -> False
    return False

_try_renew():
    lease = client.get(ns, name)
    if lease is None or holder != identity: return False
    client.replace(ns, name, body{renewTime=now, resourceVersion=rv})  # 409/404 -> False
    log "leader election: renewed"; return True
```

Logs exigidos pela issue: `leader election: acquired` (na transição para líder), `leader election: renewed` (a cada renovação bem-sucedida), `leader election: lost` (na transição para fora da liderança).

`FakeLeaseClient` (no teste): store em memória `{name: dict}` com `resourceVersion` incremental, protegido por `threading.Lock`, `clock` compartilhado. `get` retorna cópia; `create` levanta `LeaseConflictError` se já existir; `replace` levanta `LeaseConflictError` se `resourceVersion` divergir.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_acquires_leadership_when_lease_absent():
    # elector.run em thread; aguarda on_started_leading (Event);
    # assert store lease holder == identity e started chamado 1x

def test_renews_lease_periodically():
    # após adquirir, avança ManualClock(retry_period), aguarda;
    # assert renewTime > acquireTime e holder segue == identity

def test_does_not_acquire_when_other_holds_unexpired():
    # seed holder="other", renewTime=now; run; assert started NÃO chamado
    # dentro de janela curta

def test_loses_leadership_when_renew_fails_past_deadline():
    # A lidera; fake passa a retornar LeaseConflictError no replace de A;
    # assert on_stopped_leading chamado

def test_stale_renew_does_not_clobber_holder():
    # A lidera; B toma o lease (holder="B", rv novo); A tenta renew com rv
    # antigo -> 409; assert store holder == "B" (não sobrescrito)

def test_reacquires_after_lease_expires():
    # seed holder="other" com renewTime = now - 2*d; run; assert started chamado

def test_lease_deleted_externally_triggers_reacquire():
    # A lidera; store.delete(); assert on_stopped_leading e depois
    # on_started_leading (recriação)

def test_only_one_leader_at_a_time():
    # 2 electors, mesmo FakeLeaseClient, run ~0.3s; um recorder thread-safe de
    # transições (started/stopped por identity) garante que nunca há dois
    # "started" sem um "stopped" entre eles
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_leader_election.py -v`
Expected: FAIL (classe `K8sLeaderElector` não definida).

- [ ] **Step 3: Implementar `K8sLeaderElector` em `leader.py`**

Implementar `run`, `_try_acquire` e `_try_renew` conforme o pin acima, com `clock` injetável para os testes determinísticos.

- [ ] **Step 4: Rodar e confirmar passagem**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C shared run pytest tests/test_leader_election.py -v`
Expected: PASS.

- [ ] **Step 5: Lint do shared**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C shared run task lint-check`
Expected: sem diff (black/isort limpos); corrigir se necessário.

- [ ] **Step 6: Commit**

```bash
git add linx_core/shared/src/linx_shared/coordination/leader.py \
        linx_core/shared/tests/test_leader_election.py
git commit -m "feat(coordenação): implementa eleitor de líder via Lease (#273)"
```

---

### Task 3: Gating por liderança em `run_outbox_relay` e `JobReaper.run_forever`

**Files:**
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/runtime.py`
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/reaper.py`
- Test: `linx_core/services/jobs_worker/tests/test_leader_gating.py`

**Interfaces:**
- Consumes: nada de outras tasks (parâmetros novos são `threading.Event | None`).
- Produces:
  - `run_outbox_relay(stop_event, session_factory, publisher, poll_interval=1.0, max_attempts=OUTBOX_MAX_ATTEMPTS, *, leader_event: threading.Event | None = None, ready_event: threading.Event | None = None) -> None`. No topo do loop, antes de relayar: `if (leader_event is not None and not leader_event.is_set()) or (ready_event is not None and not ready_event.is_set()): stop_event.wait(poll_interval); continue`.
  - `JobReaper.run_forever(self, stop_event, *, leader_event: threading.Event | None = None, ready_event: threading.Event | None = None) -> None`. Mesma porta de gating antes de `run_once()`.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_outbox_relay_idles_when_not_leader(monkeypatch):
    # monkeypatch runtime.relay_pending_outbox com stub que incrementa contador;
    # leader_event.clear(); run em thread por ~3*poll_interval; assert contador == 0

def test_outbox_relay_runs_when_leader(monkeypatch):
    # leader_event.set() + ready_event.set(); assert contador > 0

def test_outbox_relay_waits_for_ready(monkeypatch):
    # leader_event.set() mas ready_event.clear(); assert contador == 0

def test_reaper_idles_when_not_leader(monkeypatch):
    # JobReaper(fake session_factory); monkeypatch reaper.run_once com stub;
    # leader_event.clear(); run em thread; assert contador == 0

def test_reaper_stops_when_leadership_lost():
    # leader_event.set() -> contador sobe; leader_event.clear() -> contador
    # para de subir (on_stopped_leading interrompe o loop)
```

Fake: `session_factory` retorna um objeto dummy (nunca chamado quando idle); `publisher` pode ser `FakePublisher` (de `test_outbox_relay.py`).

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest tests/test_leader_gating.py -v`
Expected: FAIL (parâmetros `leader_event`/`ready_event` inesperados → TypeError).

- [ ] **Step 3: Implementar os parâmetros e a porta de gating**

Adicionar os kw-only args às duas assinaturas e a checagem no topo de cada iteração.

- [ ] **Step 4: Rodar e confirmar passagem**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest tests/test_leader_gating.py -v`
Expected: PASS.

- [ ] **Step 5: Regressão (comportamento preservado com flag desligada)**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest tests/test_outbox_relay.py tests/test_reaper.py -v`
Expected: PASS (assinatura antiga continua válida via defaults).

- [ ] **Step 6: Commit**

```bash
git add linx_core/services/jobs_worker/src/jobs_worker/runtime.py \
        linx_core/services/jobs_worker/src/jobs_worker/reaper.py \
        linx_core/services/jobs_worker/tests/test_leader_gating.py
git commit -m "feat(jobs_worker): condiciona loops singleton à liderança (#273)"
```

---

### Task 4: Config (`WorkerSettings`) e integração no `main()`

**Files:**
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/config.py`
- Modify: `linx_core/services/jobs_worker/src/jobs_worker/main.py`
- Test: `linx_core/services/jobs_worker/tests/test_startup_config.py`

**Interfaces:**
- Consumes: `K8sLeaderElector`, `InClusterLeaseClient`, `resolve_identity` (Task 2); parâmetros de gating (Task 3).
- Produces (em `WorkerSettings`, `config.py`):
  - `leader_election_enabled: bool = False`
  - `leader_election_lease_name: str = "jobs-worker"`
  - `leader_election_namespace: str = "linx"`
  - `leader_election_identity: str = ""`
  - `leader_election_lease_duration_seconds: int = 15`
- Produces (em `main.py`):
  - `def _wait_for_dependencies_background(stop_event: threading.Event, ready_event: threading.Event) -> None` — loop `check()` + `SELECT 1 FROM jobs LIMIT 1`; em sucesso `ready_event.set()` e retorna; em falha loga warning e `stop_event.wait(READY_DELAY_SECONDS)`; nunca levanta.

Fluxo `main()` quando `settings.leader_election_enabled`:
1. `stop_event`, `leader_event = threading.Event()`, `ready_event = threading.Event()`.
2. Construir `K8sLeaderElector` com `client=InClusterLeaseClient()`, `identity=resolve_identity(settings.leader_election_identity)`, `namespace=settings.leader_election_namespace`, `lease_name=settings.leader_election_lease_name`, `lease_duration_seconds=settings.leader_election_lease_duration_seconds`, `on_started_leading=lambda: (leader_event.set(), logger.info("leader election: acquired"))`, `on_stopped_leading=lambda: (leader_event.clear(), logger.info("leader election: lost"))`.
3. Iniciar `threading.Thread(target=elector.run, args=(stop_event,), name="leader-elector", daemon=True)` **antes** de qualquer espera de dependência.
4. Iniciar `threading.Thread(target=_wait_for_dependencies_background, args=(stop_event, ready_event), name="deps-wait", daemon=True)`.
5. NÃO chamar `_wait_for_dependencies()` fatal nem `_declare_topology()` eager (os `run_consumer` declaram via callback).
6. Passar `leader_event=leader_event, ready_event=ready_event` às threads de `outbox-relay` e `job-reaper`.

Fluxo `main()` quando `leader_election_enabled` é falso: exatamente o código atual (fatal `_wait_for_dependencies()`, `_declare_topology()` eager, sem args de gating).

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_worker_settings_leader_election_defaults():
    # WorkerSettings() (sem env) -> leader_election_enabled is False,
    # lease_name == "jobs-worker", namespace == "linx",
    # lease_duration_seconds == 15, identity == ""

def test_worker_settings_leader_election_env(monkeypatch):
    # LEADER_ELECTION_ENABLED=true, LEADER_ELECTION_LEASE_NAME=x,
    # LEADER_ELECTION_NAMESPACE=y, LEADER_ELECTION_LEASE_DURATION_SECONDS=30
    # -> campos refletem os valores
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest tests/test_startup_config.py -v`
Expected: FAIL (campos inexistentes em `WorkerSettings`).

- [ ] **Step 3: Implementar campos e o fluxo no `main()`**

Adicionar os campos em `WorkerSettings` (pydantic-settings mapeia `LEADER_ELECTION_*` automaticamente). Refatorar `main()` conforme o fluxo acima.

- [ ] **Step 4: Rodar e confirmar passagem**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C services/jobs_worker run pytest tests/test_startup_config.py -v`
Expected: PASS.

- [ ] **Step 5: Lint do jobs_worker**

Run: `cd linx_core && env -u VIRTUAL_ENV poetry -C services/jobs_worker run task lint-check`
Expected: sem diff; corrigir se necessário.

- [ ] **Step 6: Commit**

```bash
git add linx_core/services/jobs_worker/src/jobs_worker/config.py \
        linx_core/services/jobs_worker/src/jobs_worker/main.py \
        linx_core/services/jobs_worker/tests/test_startup_config.py
git commit -m "feat(jobs_worker): integra eleição de líder no startup (#273)"
```

---

### Task 5: Manifests Kubernetes (Deployment + RBAC + config)

**Files:**
- Create: `infra/kubernetes/base/jobs-worker.yaml`
- Modify: `infra/kubernetes/base/linx-config.yaml`
- Modify: `infra/kubernetes/base/kustomization.yaml`
- Modify: `infra/kubernetes/linx-secrets.example.env`

**Interfaces:**
- Consumes: imagem `includeluisferreira/jobs-worker:dev` (publicada no Task 6); `linx-config`/`linx-secrets` existentes.
- Produces: `Deployment` `jobs-worker` (replicas 3), `ServiceAccount` `jobs-worker`, `Role` `jobs-worker-leader-election`, `RoleBinding` idem.

Conteúdo de `jobs-worker.yaml` (seguir padrão de `identity-api.yaml`):
- `Deployment` `jobs-worker`: `replicas: 3`; initContainer `wait-for-db` (`python -m linx_shared.db.wait`) com `envFrom` `linx-config` + `linx-secrets`; container `jobs-worker` com imagem `includeluisferreira/jobs-worker:dev`, `imagePullPolicy: Always`, `envFrom` `linx-config` + `linx-secrets`; `serviceAccountName: jobs-worker`; sem porta (worker puro; liveness/readiness via `exec` do healthcheck do Dockerfile é opcional — usar `startupProbe`? Não: manter sem probes ou com liveness por `exec` do health check; decisão do implementador: mínimo é não bloquear).
- `ServiceAccount` `jobs-worker` (namespace `linx`).
- `Role` `jobs-worker-leader-election` com `apiGroups: ["coordination.k8s.io"]`, `resources: ["leases"]`, `verbs: ["get", "create", "update", "patch"]`.
- `RoleBinding` `jobs-worker-leader-election` ligando o SA à Role.

`linx-config.yaml` ganha (não-secretas):
```yaml
  LEADER_ELECTION_ENABLED: "true"
  LEADER_ELECTION_LEASE_NAME: "jobs-worker"
  LEADER_ELECTION_NAMESPACE: "linx"
```

`linx-secrets.example.env` ganha a chave `RABBITMQ_AMQP_URL` (placeholder `amqp://change-me:change-me@rabbitmq.linx.svc.cluster.local:5672/`).

`kustomization.yaml` (base): adicionar `- jobs-worker.yaml`.

- [ ] **Step 1: Criar os manifests e as variáveis**

- [ ] **Step 2: Validar render**

Run: `kubectl kustomize infra/kubernetes >/dev/null && echo ok`
Expected: `ok` (render da base sem erro).

- [ ] **Step 3: Validar dry-run**

Run: `kubectl apply -k infra/kubernetes --dry-run=client >/dev/null && echo ok`
Expected: `ok` (se cluster acessível; senão, registrar `kubectl kustomize` como evidência).

- [ ] **Step 4: Commit**

```bash
git add infra/kubernetes/base/jobs-worker.yaml \
        infra/kubernetes/base/linx-config.yaml \
        infra/kubernetes/base/kustomization.yaml \
        infra/kubernetes/linx-secrets.example.env
git commit -m "feat(k8s): adiciona Deployment e RBAC do jobs_worker (#273)"
```

---

### Task 6: Workflow de publicação da imagem + CI de manifests

**Files:**
- Create: `.github/workflows/publish-jobs-worker-image.yml`
- Modify: `.github/workflows/k8s-ci.yml`

**Interfaces:**
- Consumes: `publish-linx-core-image.yml` (workflow_call reutilizável) com inputs `service`, `dockerfile`, `repository`, `context`.
- Produces: imagem `includeluisferreira/jobs-worker` (tags `dev`/`latest`/`sha-<short>`).

`publish-jobs-worker-image.yml` (espelhar `publish-agent-bridge-image.yml`): `workflow_call` para `publish-linx-core-image.yml` com `service: jobs-worker`, `dockerfile: services/jobs_worker/Dockerfile`, `repository: includeluisferreira/jobs-worker`, `context: linx_core`; `push` em `develop`/`main` com `paths` `linx_core/services/jobs_worker/**` + `linx_core/shared/**` + os dois arquivos de workflow; `workflow_dispatch`.

`k8s-ci.yml`: estender a checagem de render da base para também exigir os novos kinds:
```yaml
echo "$out" | grep -Eq 'kind: (Namespace|ConfigMap|PersistentVolumeClaim|Deployment|Service|ServiceAccount|Role|RoleBinding)'
```

- [ ] **Step 1: Criar o workflow e ajustar o CI**

- [ ] **Step 2: Validar sintaxe do workflow (local, opcional)**

Run: `actionlint .github/workflows/publish-jobs-worker-image.yml` (se `actionlint` disponível; senão, revisar manualmente).
Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish-jobs-worker-image.yml \
        .github/workflows/k8s-ci.yml
git commit -m "ci(k8s): publica imagem do jobs_worker e valida RBAC (#273)"
```

---

### Task 7: README de evidências (aceite)

**Files:**
- Modify: `infra/kubernetes/README.md`

**Interfaces:** nenhuma (documentação).

Conteúdo a acrescentar:
- Tabela de imagens: linha `jobs-worker` → `includeluisferreira/jobs-worker:dev`.
- Seção "Eleição de líder" explicando o `Lease`, o RBAC mínimo e as variáveis `LEADER_ELECTION_*`.
- Seção de evidências (Entrega 3) com os comandos exatos:

```bash
kubectl -n linx get lease -w                       # muda de titular ao trocar líder
kubectl -n linx get lease jobs-worker -o yaml      # holderIdentity atual
kubectl -n linx logs deploy/jobs-worker -c jobs-worker | grep "leader election"
kubectl -n linx delete pod -l app=jobs-worker --field-selector=spec.nodeName=... # ou deletar o líder pelo nome
kubectl -n linx get pods -o wide                   # 3x jobs-worker Running
```

- Tabela requisito → mecanismo → arquivo → evidência, cobrindo RF-040/RF-041/RF-042 e eleição de líder (linkando `migration_lock.py` e `repository.py` como evidência de exclusão mútua já existente, sem reimplementar).

- [ ] **Step 1: Atualizar o README**

- [ ] **Step 2: Commit**

```bash
git add infra/kubernetes/README.md
git commit -m "docs(k8s): evidências de eleição de líder no jobs_worker (#273)"
```

---

## Self-Review (verificado pelo autor)

- **Spec coverage:** decisões D1 (HTTP in-cluster → Task 1), D2 (workflow → Task 6), D3 (eleição independente → Task 4) e escopo da issue (leader.py → Tasks 1–2; integração → Tasks 3–4; manifests → Task 5; testes → Tasks 1–4; evidências → Task 7) — todas mapeadas.
- **Step scan:** cada step tem um comando e um resultado esperado; algoritmos não-óbvios (run loop, gating) têm pin de comportamento, não transcrição.
- **Type consistency:** `leader_event`/`ready_event` nomeados idênticos em Tasks 3 e 4; `K8sLeaderElector`/`InClusterLeaseClient`/`resolve_identity` idênticos entre Tasks 1, 2 e 4.
- **Review Focus:** os 5 casos têm teste mapeado na task dona (Task 1/Task 2/Task 3/Task 4), listados na seção Review Focus.
- **Proportion:** plano conciso; corpos substituídos por assinaturas e asserções; o pin do algoritmo do eleitor é o mínimo necessário para os testes.

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-11-07-leader-election-jobs-worker.md`. Aguardando revisão e escolha do método de execução antes de implementar.
