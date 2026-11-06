# Service Discovery k8s + UUIDv4 em Envelopes — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Restrição desta sessão:** commits e push SOMENTE após autorização explícita do usuário. Os passos de commit ficam no plano para referência do executor futuro.

**Goal:** Expor `agent_bridge` e `identity_api` no k3s via CoreDNS (`<svc>.linx.svc.cluster.local`) e fechar a lacuna de UUIDv4 no envelope AMQP de telemetria.

**Architecture:** Manifestos declarativos em `deploy/k8s/` aplicáveis com `kubectl apply -k` (kustomization nativa do kubectl, sem Helm). Um Postgres mínimo (1 réplica + PVC `local-path` do k3s) sustenta as dependências de banco dentro do cluster para que as evidências (DNS, `grpcurl`, `/health`) sejam reais, não só `dry-run`. Imagens construídas localmente e importadas no cluster (k3d/kind local; `k3s ctr images import` na sandbox AWS — Learner Lab não tem registry).

**Tech Stack:** Kubernetes (k3s, apps/v1), kubectl kustomize, Postgres 15-alpine, Python 3.12, pytest.

**Spec:** Issue #257 — https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/257

## Fatos verificados no código (não re-decidir)

- `identity_api`: porta **8000**, `/health` público (`main.py:52`), entrypoint `docker-entrypoint.sh` roda `alembic upgrade head` com 30 retries e depois `uvicorn`. Envs: `DATABASE_URL`, `ENVIRONMENT`, `CHIRPSTACK_HOST`, `CHIRPSTACK_API_TOKEN`, `SERVICE_TOKEN`, `RABBITMQ_MANAGEMENT_URL`, `RABBITMQ_ADMIN_USER`, `RABBITMQ_ADMIN_PASSWORD`, `RABBITMQ_VHOST`, `RABBITMQ_TENANT_SECRET`, `RABBITMQ_AMQP_HOST`.
- `agent_bridge`: porta **50051** (`config.py:7`), sem HTTP → probe `tcpSocket`. Envs: `DATABASE_URL`, `GRPC_HOST=0.0.0.0`, `GRPC_PORT=50051`, `AGENT_SERVICE_TOKEN`.
- `linx_shared/core/config.py` rejeita segredos placeholder/vazios no startup (`require_secret`, `require_connection_string`) → pod sem Secret sobe e morre (CrashLoopBackOff). Esperado: criar o Secret **antes** do apply.
- Compose (`deploy/docker-compose.yml`) só define `build:`, sem nome de imagem → este plano fixa `linx/identity-api:dev` e `linx/agent-bridge:dev`.
- UUIDv4 REST já entregue na PR #252: `linx_shared/core/uuid4.py`, rotas e schemas do `identity_api`, testes `test_uuid_enforcement.py` e `linx_core/shared/tests/test_uuid4.py`. **Gap restante:** `middleware/services/routing/src/routing/envelope.py` (envelope AMQP de telemetria) não tem campo de identificador único.
- k3s provisiona PVCs via `local-path` por default → PVC funciona sem configuração extra.

## Global Constraints

- Namespace fixo: `linx`. Labels: `app: <nome-do-servico>`. APIs estáveis (`apps/v1`, `v1`).
- Nenhum segredo real commitado: apenas `linx-secrets.example.env`; o Secret real é criado imperativamente (AGENTS.md §5).
- Commits: Conventional Commits em português com `(#257)`; `git add` arquivo por arquivo; push só com autorização.
- Validação de manifesto: `kubectl apply -k deploy/k8s --dry-run=client` deve passar sem erro antes de cada commit.
- `pytest` do serviço tocado deve passar antes do commit (config em `pyproject.toml`).
- Limitação conhecida a registrar no README/relatório: LB de Service ClusterIP é L4 (por conexão); conexão gRPC longa fica presa a um pod. Headless service + client-side LB fica fora de escopo.

## Review Focus

1. **ImagePullBackOff**: imagem `linx/*:dev` não existe no cluster → Task 5 torna build+import passo obrigatório e verifica com `kubectl get pods -n linx`.
2. **Race de migrations com `replicas: 2`**: dois pods rodando `alembic upgrade head` ao mesmo tempo → Task 3 move migração para `initContainer` único por pod e o container principal sobe só o uvicorn (entrypoint do compose permanece intacto para o compose).
3. **Secret ausente**: pods morrem no startup validator → Task 1 cria o `.example` e Task 5 exige `kubectl create secret` antes do `apply`; verificação via `kubectl describe pod`.
4. **Selector mismatch** Deployment↔Service → endpoints vazios → verificação `kubectl -n linx get endpoints agent-bridge identity-api` na Task 5.
5. **`envelope_id` novo quebrar consumidor**: campo é aditivo (consumidor lê chaves conhecidas) → Task 4 roda também os testes de `telemetry_consumer` como regressão.

---

### Task 1: Namespace, Postgres mínimo, ConfigMap, Secret example, kustomization

**Files:**
- Create: `deploy/k8s/namespace.yaml`
- Create: `deploy/k8s/postgres.yaml`
- Create: `deploy/k8s/linx-config.yaml`
- Create: `deploy/k8s/linx-secrets.example.env`
- Create: `deploy/k8s/kustomization.yaml`

**Interfaces:**
- Produces: namespace `linx`; Service DNS `postgres.linx.svc.cluster.local:5432`; ConfigMap `linx-config` (chaves: `GRPC_HOST=0.0.0.0`, `GRPC_PORT=50051`, `ENVIRONMENT=production`, `CHIRPSTACK_HOST`, `RABBITMQ_AMQP_HOST`, `RABBITMQ_MANAGEMENT_URL`, `RABBITMQ_VHOST=/`); Secret `linx-secrets` (chaves esperadas: `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SERVICE_TOKEN`, `AGENT_SERVICE_TOKEN`, `CHIRPSTACK_API_TOKEN`, `RABBITMQ_ADMIN_USER`, `RABBITMQ_ADMIN_PASSWORD`, `RABBITMQ_TENANT_SECRET`). Tasks 2 e 3 consomem esses nomes.

- [ ] **Step 1: Criar `deploy/k8s/namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: linx
```

- [ ] **Step 2: Criar `deploy/k8s/postgres.yaml`**

Deployment `postgres` (1 réplica — banco não se escala com `replicas`), imagem `postgres:15-alpine`, env `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` vindos de `secretRef: linx-secrets`, `readinessProbe` exec `pg_isready -U $(POSTGRES_USER) -d $(POSTGRES_DB)`, `volumeMounts` em `/var/lib/postgresql/data` via PVC `postgres-data` (1Gi, `storageClassName: local-path`), Service ClusterIP `postgres` porta 5432. Comentário no arquivo: "Postgres efêmero para evidência de service discovery; dados de produção não pertencem a este manifest".

- [ ] **Step 3: Criar `deploy/k8s/linx-config.yaml`**

ConfigMap `linx-config` com as chaves não-sensíveis listadas em Interfaces. Hosts internos apontam para nomes DNS do cluster (ex.: `RABBITMQ_AMQP_HOST: rabbitmq.linx.svc.cluster.local:5672` com comentário de que RabbitMQ no k8s é pendência — valor informativo, não bloqueia os pods desta issue).

- [ ] **Step 4: Criar `deploy/k8s/linx-secrets.example.env`**

Template com as chaves de Interfaces e valores placeholder (`change-me`), com header de comentário: "copie para linx-secrets.env (NÃO commitar), preencha, e crie com `kubectl create secret generic linx-secrets -n linx --from-env-file=linx-secrets.env`". Adicionar `deploy/k8s/linx-secrets.env` ao `.gitignore`.

- [ ] **Step 5: Criar `deploy/k8s/kustomization.yaml`**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - postgres.yaml
  - linx-config.yaml
  - agent-bridge.yaml   # Task 2
  - identity-api.yaml   # Task 3
```
Comentar as duas últimas linhas até as Tasks 2/3 existirem, ou criar os arquivos na sequência antes de validar.

- [ ] **Step 6: Validar dry-run**

Run: `kubectl apply -k deploy/k8s --dry-run=client`
Expected: recursos de namespace/postgres/configmap criados (dry-run), sem erro de schema.

- [ ] **Step 7: Commit** (aguardando autorização)

```bash
git add deploy/k8s/namespace.yaml deploy/k8s/postgres.yaml deploy/k8s/linx-config.yaml deploy/k8s/linx-secrets.example.env deploy/k8s/kustomization.yaml .gitignore
git commit -m "feat(k8s): namespace, postgres minimo e config base para service discovery (#257)"
```

---

### Task 2: Deployment + Service do agent-bridge

**Files:**
- Create: `deploy/k8s/agent-bridge.yaml`

**Interfaces:**
- Consumes: namespace `linx`, ConfigMap `linx-config`, Secret `linx-secrets` (Task 1).
- Produces: Service DNS `agent-bridge.linx.svc.cluster.local:50051`; Deployment `agent-bridge` com label `app: agent-bridge`.

- [ ] **Step 1: Criar `deploy/k8s/agent-bridge.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-bridge
  namespace: linx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: agent-bridge
  template:
    metadata:
      labels:
        app: agent-bridge
    spec:
      containers:
        - name: agent-bridge
          image: linx/agent-bridge:dev
          imagePullPolicy: IfNotPresent
          ports:
            - name: grpc
              containerPort: 50051
          envFrom:
            - configMapRef: {name: linx-config}
            - secretRef: {name: linx-secrets}
          readinessProbe:
            tcpSocket: {port: grpc}
            periodSeconds: 10
          livenessProbe:
            tcpSocket: {port: grpc}
            periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: agent-bridge
  namespace: linx
spec:
  selector:
    app: agent-bridge
  ports:
    - name: grpc
      port: 50051
      targetPort: grpc
```

- [ ] **Step 2: Validar dry-run**

Run: `kubectl apply -f deploy/k8s/agent-bridge.yaml --dry-run=client`
Expected: `deployment.apps/agent-bridge created (dry run)` + `service/agent-bridge created (dry run)`.

- [ ] **Step 3: Commit** (aguardando autorização)

```bash
git add deploy/k8s/agent-bridge.yaml deploy/k8s/kustomization.yaml
git commit -m "feat(k8s): Deployment e Service do agent-bridge com DNS interno (#257)"
```

---

### Task 3: Deployment + Service do identity-api

**Files:**
- Create: `deploy/k8s/identity-api.yaml`

**Interfaces:**
- Consumes: Task 1 (namespace/config/secret), `postgres` Service.
- Produces: Service DNS `identity-api.linx.svc.cluster.local:8000`; padrão initContainer-de-migração que outros serviços FastAPI futuros copiam.

- [ ] **Step 1: Criar `deploy/k8s/identity-api.yaml`**

Deployment `identity-api`, `replicas: 2`, label `app: identity-api`, imagem `linx/identity-api:dev`, `envFrom` configmap+secret. **initContainer `migrate`** com `command: ["python", "-m", "alembic", "-c", "/app/alembic.ini", "upgrade", "head"]` (mesma imagem; evita a race de migrations do entrypoint entre as 2 réplicas — ver Review Focus 2). Container principal com `command: ["python", "-m", "uvicorn", "identity_api.main:app", "--host", "0.0.0.0", "--port", "8000"]` (sobrescreve o entrypoint do compose; o `docker-entrypoint.sh` continua sendo o caminho do compose). Probes: `httpGet /health` porta 8000 (readiness `periodSeconds: 10`, liveness `periodSeconds: 20`, `failureThreshold: 3`). Service ClusterIP `identity-api` porta 8000.

- [ ] **Step 2: Validar dry-run**

Run: `kubectl apply -f deploy/k8s/identity-api.yaml --dry-run=client`
Expected: `deployment.apps/identity-api created (dry run)` + `service/identity-api created (dry run)`.

- [ ] **Step 3: Commit** (aguardando autorização)

```bash
git add deploy/k8s/identity-api.yaml deploy/k8s/kustomization.yaml
git commit -m "feat(k8s): Deployment e Service do identity-api com initContainer de migrations (#257)"
```

---

### Task 4: UUIDv4 no envelope AMQP de telemetria

**Files:**
- Modify: `middleware/services/routing/src/routing/envelope.py`
- Test: `middleware/services/routing/tests/test_envelope.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `build_envelope(uplink) -> dict` passa a incluir `envelope_id: str` (UUIDv4). Consumidores (`telemetry_consumer`) leem chaves conhecidas — campo é aditivo e retrocompatível.

- [ ] **Step 1: Escrever o teste que falha**

Em `middleware/services/routing/tests/test_envelope.py`, adicionar:

```python
def test_envelope_has_uuid4_id():
    envelope = build_envelope(make_valid_uplink())  # fixture/factory já existente no arquivo
    parsed = uuid.UUID(envelope["envelope_id"])
    assert parsed.version == 4
    assert envelope["envelope_id"] == str(parsed)
```

(Adaptar ao factory de uplink já existente no arquivo de teste; reutilizar o helper do repo `linx_shared/core/uuid4.py` se aplicável ao middleware — verificar dependência do middleware em `linx_shared`; se não houver, usar `uuid.uuid4()` da stdlib.)

- [ ] **Step 2: Rodar o teste e vê-lo falhar**

Run: `cd middleware/services/routing && python -m pytest tests/test_envelope.py -v`
Expected: FAIL — `KeyError: 'envelope_id'`.

- [ ] **Step 3: Implementar `envelope_id` em `envelope.py`**

Adicionar `"envelope_id": str(uuid.uuid4())` ao dict em `build_envelope`, com comentário de uma linha: identificador único do envelope (Entrega 3, #257).

- [ ] **Step 4: Rodar testes do routing e regressão do consumer**

Run: `cd middleware/services/routing && python -m pytest tests/ -v`
Expected: PASS.
Run: `cd client/services/telemetry_consumer && python -m pytest tests/ -v`
Expected: PASS (campo aditivo não quebra consumidor).

- [ ] **Step 5: Comentar na issue #258**

Registrar que o interceptor gRPC da #258 deve injetar também `x-request-id: <uuid4>` na metadata, cobrindo o requisito de UUIDv4 nos payloads gRPC sem alterar os `.proto`.

- [ ] **Step 6: Commit** (aguardando autorização)

```bash
git add middleware/services/routing/src/routing/envelope.py middleware/services/routing/tests/test_envelope.py
git commit -m "feat(routing): envelope_id UUIDv4 no envelope AMQP de telemetria (#257)"
```

---

### Task 5: README de operação e evidências de validação

**Files:**
- Create: `deploy/k8s/README.md`

**Interfaces:**
- Consumes: todos os manifests das Tasks 1–3.
- Produces: runbook reproduzível usado no relatório técnico da Entrega 3.

- [ ] **Step 1: Escrever `deploy/k8s/README.md`**

Seções (português):
1. **Pré-requisitos**: k3d (`k3d cluster create linx`) ou acesso ao k3s da sandbox (`infra/k3s-aws-sandbox`); `kubectl`; `grpcurl`; imagem `busybox` para teste de DNS.
2. **Build das imagens**: `docker build -t linx/identity-api:dev -f linx_core/services/identity_api/Dockerfile linx_core` e `docker build -t linx/agent-bridge:dev -f linx_core/services/agent_bridge/Dockerfile linx_core`.
3. **Import no cluster**: local `k3d image import -c linx linx/identity-api:dev linx/agent-bridge:dev`; sandbox AWS `docker save ... | ssh ... 'sudo k3s ctr images import -'`.
4. **Secret**: copiar `linx-secrets.example.env` → `linx-secrets.env`, preencher, `kubectl create secret generic linx-secrets -n linx --from-env-file=deploy/k8s/linx-secrets.env`.
5. **Apply**: `kubectl apply -k deploy/k8s`.
6. **Evidências** (comandos + saída esperada): ver Step 2.

- [ ] **Step 2: Bloco de evidências no README (comandos exatos)**

```bash
kubectl -n linx get pods -o wide                                  # 2x agent-bridge, 2x identity-api Running
kubectl -n linx get endpoints agent-bridge identity-api           # endpoints não vazios (selector OK)
kubectl -n linx run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup agent-bridge.linx.svc.cluster.local                    # resolve para o ClusterIP
kubectl -n linx run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup identity-api.linx.svc.cluster.local
kubectl -n linx port-forward svc/agent-bridge 50051:50051 &
grpcurl -plaintext localhost:50051 list                           # lista serviço linx.agent.AgentBridge
kubectl -n linx port-forward svc/identity-api 8000:8000 &
curl -s http://localhost:8000/health                              # {"status": "ok"} ou equivalente
kubectl -n linx logs deploy/identity-api -c migrate --tail=5      # migrations aplicadas 1x por pod
```

- [ ] **Step 3: Validar README**

Seguir o runbook do zero em cluster local (k3d). Toda evidência do Step 2 precisa sair como descrito; corrigir o que divergir.

- [ ] **Step 4: Commit** (aguardando autorização)

```bash
git add deploy/k8s/README.md
git commit -m "docs(k8s): runbook de deploy e evidencias de service discovery (#257)"
```

---

## Self-Review

- **Cobertura do spec (#257):** manifests k8s + CoreDNS → Tasks 1–3 e 5; UUIDv4 envelopes/payloads → Task 4 (AMQP) + evidência REST já existente (#252) + passo 5 da Task 4 (gRPC via #258). Sem gaps.
- **Passos:** cada passo tem comando ou decisão única; bodies de código só onde o valor exato é o deliverable (manifests) ou cópia fixa.
- **Consistência de tipos/nomes:** `linx-config`, `linx-secrets`, `agent-bridge`, `identity-api`, `postgres`, namespace `linx` usados de forma idêntica em todas as tasks.
- **Review Focus:** 5 itens, todos com passo de verificação na task dona.
- **Proporção:** manifestos são o deliverable; demais passos são comandos e asserções.
