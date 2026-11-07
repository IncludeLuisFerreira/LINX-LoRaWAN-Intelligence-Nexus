# Service Discovery no k3s (issue #257)

Manifestos Kubernetes para expor `agent_bridge` e `identity_api` internamente via
CoreDNS do k3s. Namespace `linx`, aplicação via `kubectl apply -k`.

No caminho padrão as imagens são públicas no Docker Hub e o cluster as puxa
automaticamente. Não é necessário buildar nem importar imagens localmente; o
fallback offline existe apenas para clusters sem acesso a registry.

## Pré-requisitos

- Cluster k3s local (recomendado: `k3d cluster create linx`) **ou** acesso ao
  k3s da sandbox provisionado por `infra/k3s-aws-sandbox`.
- `kubectl` (context apontando para o cluster).
- `grpcurl` (evidência gRPC).
- Imagem `busybox` para o teste de DNS.
- Acesso ao Docker Hub para o fluxo padrão (as imagens são públicas).

## Criar o cluster local (k3d)

Pule esta seção apenas se já tiver um cluster acessível. Se você executou a
limpeza/reset ou o contexto `kubectl` sumiu, **crie o cluster antes de tudo** —
sem ele, o apply falha.

```bash
k3d cluster create linx
kubectl wait --for=condition=Ready node/k3d-linx-server-0 --timeout=180s
kubectl config current-context   # deve mostrar k3d-linx
```

## Imagens padrão (Docker Hub)

| Serviço | Imagem padrão |
| --- | --- |
| `identity-api` | `includeluisferreira/identity-api:dev` |
| `agent-bridge` | `includeluisferreira/agent-bridge:dev` |

Os repositórios são públicos e a base usa `imagePullPolicy: Always`, porque a tag
`dev` é mutável. O cluster puxa as imagens no primeiro agendamento; **não há
`ctr images import` no caminho padrão**.

Tags publicadas pelo CI: `dev` (branch `develop`), `latest` (branch `main`) e
`sha-<short-sha>` (ambas as branches, imutável). Use `sha-*` ou um digest para
produção e rollback; veja [Publicação das imagens](#publicação-das-imagens-github-actions).

### Build local opcional (debug)

Necessário apenas para testar alterações antes de publicar. Use
`--platform linux/amd64` para coincidir com as imagens publicadas e com os nós
do cluster:

```bash
docker build --platform linux/amd64 \
  -t includeluisferreira/identity-api:dev \
  -f linx_core/services/identity_api/Dockerfile linx_core
docker build --platform linux/amd64 \
  -t includeluisferreira/agent-bridge:dev \
  -f linx_core/services/agent_bridge/Dockerfile linx_core
```

Para usar a imagem local sem publicar, siga o fallback offline abaixo.

### Fallback offline (sem acesso ao registry)

Este **não é o fluxo normal**; use somente quando o cluster não conseguir puxar
do Docker Hub. Importe a imagem já buildada com o mesmo nome que o manifest
espera, direto no containerd do nó:

```bash
# k3d local
# Não use `k3d image import`: o modo padrão sofre race (k3d#1484) e o
# --mode=direct pode travar em deadlock no k3d v5.9.0. Importe direto no
# containerd do nó do cluster:
SERVER_NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
docker save includeluisferreira/identity-api:dev includeluisferreira/agent-bridge:dev \
  | docker exec -i "$SERVER_NODE" ctr -n k8s.io images import -
```

```bash
# sandbox AWS (sem registry)
docker save includeluisferreira/identity-api:dev includeluisferreira/agent-bridge:dev \
  | ssh <host> 'sudo k3s ctr images import -'
```

Como a base usa `imagePullPolicy: Always`, o kubelet ainda tentaria o registry.
Depois do import, troque a política para `IfNotPresent` **apenas neste ambiente**
(não versione essa mudança). O namespace e o Secret precisam existir antes do
apply (veja a seção seguinte). Aplique primeiro e faça o patch em seguida; os
pods podem ficar em `ImagePullBackOff` até a política nova chegar:

```bash
kubectl apply -k deploy/k8s

kubectl -n linx patch deployment identity-api --type=strategic -p '{
  "spec":{"template":{"spec":{
    "initContainers":[
      {"name":"wait-for-db","imagePullPolicy":"IfNotPresent"},
      {"name":"migrate","imagePullPolicy":"IfNotPresent"}
    ],
    "containers":[
      {"name":"identity-api","imagePullPolicy":"IfNotPresent"}
    ]
  }}}
}'

kubectl -n linx patch deployment agent-bridge --type=strategic -p '{
  "spec":{"template":{"spec":{
    "initContainers":[
      {"name":"wait-for-db","imagePullPolicy":"IfNotPresent"}
    ],
    "containers":[
      {"name":"agent-bridge","imagePullPolicy":"IfNotPresent"}
    ]
  }}}
}'
```

## Namespace e Secret

Nenhum segredo real é commitado. O namespace precisa existir **antes** do
Secret; crie-o primeiro e depois copie/preencha o template. Os serviços rejeitam
placeholders (`change-me`) no startup:

```bash
kubectl apply -f deploy/k8s/namespace.yaml

cp deploy/k8s/linx-secrets.example.env deploy/k8s/linx-secrets.env
# editar linx-secrets.env; no laboratório DATABASE_URL aponta para
# postgres.linx.svc.cluster.local:5432

# idempotente: pode rodar de novo sem "AlreadyExists"
kubectl create secret generic linx-secrets -n linx \
  --from-env-file=deploy/k8s/linx-secrets.env \
  --dry-run=client -o yaml | kubectl apply -f -
```

O `--dry-run=client -o yaml` gera o Secret e o `kubectl apply` o cria ou
atualiza, sem falhar em execuções repetidas. As chaves mínimas são as do
template: `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`SERVICE_TOKEN`, `AGENT_SERVICE_TOKEN`, `CHIRPSTACK_API_TOKEN`,
`RABBITMQ_ADMIN_USER`, `RABBITMQ_ADMIN_PASSWORD` e `RABBITMQ_TENANT_SECRET`.

`deploy/k8s/linx-secrets.env` está no `.gitignore` — nunca versionar.

### Banco externo (RDS, Cloud SQL etc.)

Para apontar para um banco gerenciado, altere **somente** `DATABASE_URL` em
`deploy/k8s/linx-secrets.env` (usuário, senha, host, porta e database) e recrie o
Secret com o comando acima. Nenhum manifest precisa mudar. Exemplo de formato:

```dotenv
DATABASE_URL=postgresql+psycopg://<user>:<pass>@<host>:5432/<database>
```

O `postgres` do laboratório (`postgres.linx.svc.cluster.local`) continua no
manifest, mas os serviços usam o host definido no Secret.

## Migrations e probes

O `identity-api` aplica migrations antes de subir a aplicação:

1. InitContainer `wait-for-db` executa `python -m linx_shared.db.wait`, que tenta
   um `SELECT 1` a cada 2s por até 60s. URL inválida falha rápido com mensagem
   clara; se o timeout expirar, o initContainer falha e o pod reinicia.
2. InitContainer `migrate` executa `alembic upgrade head` uma única vez.
3. O container principal `identity-api` só inicia o `uvicorn` depois que os dois
   initContainers terminam. O `docker-entrypoint.sh` continua sendo o caminho do
   Compose.

O `migrations/env.py` adquire um advisory lock do PostgreSQL
(`pg_advisory_lock`, chave `927351`) em uma conexão dedicada antes de aplicar as
migrations e o libera no `finally`. Com `replicas: 2`, a segunda réplica espera a
primeira terminar em vez de disputar a tabela `alembic_version` — as duas rodam
o initContainer, mas só uma aplica migrations de fato. Se o processo morrer, a
conexão fecha e o Postgres libera o lock.

Probes do `identity-api`:

- **Readiness:** `GET /health` na porta 8000. Retorna 503 quando o banco não
  responde, removendo o pod dos endpoints.
- **Liveness:** `tcpSocket` na porta 8000. Não depende do banco: uma
  indisponibilidade do Postgres não reinicia todos os pods em loop.

O `agent-bridge` usa `tcpSocket` na porta 50051 para readiness e liveness, pois
não expõe HTTP. O `wait-for-db` cobre a disponibilidade inicial do banco. O
`postgres` usa `pg_isready` em readiness e liveness.

## Apply e overlays

Caminho padrão (Docker Hub):

```bash
kubectl apply -k deploy/k8s
```

O overlay `dockerhub` apenas referencia a mesma base e serve como comando
explícito para o laboratório:

```bash
kubectl apply -k deploy/overlays/dockerhub
```

### Exemplo ECR (AWS/empresa)

`deploy/overlays/ecr` é um **exemplo editável**, não um overlay pronto para
aplicar: o Kustomize não interpola variáveis de ambiente. Copie ou edite o
arquivo e substitua `<AWS_ACCOUNT_ID>`, `<AWS_REGION>` e `<SHORT_SHA>`:

```yaml
# deploy/overlays/ecr/kustomization.yaml (trecho)
images:
  - name: includeluisferreira/identity-api
    newName: <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/identity-api
    newTag: sha-<SHORT_SHA>
  - name: includeluisferreira/agent-bridge
    newName: <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/agent-bridge
    newTag: sha-<SHORT_SHA>
```

Valide a sintaxe e aplique depois de editar:

```bash
kubectl kustomize deploy/overlays/ecr >/dev/null
kubectl apply -k deploy/overlays/ecr
```

Se tiver o binário `kustomize`, também pode usar
`kustomize edit set image` no diretório do overlay. Para registry privado,
descomente o patch de `imagePullSecrets` no `kustomization.yaml` e crie o Secret
`regcred` no namespace `linx`.

## Publicação das imagens (GitHub Actions)

Dois workflows publicam as imagens a partir de `develop` e `main`, além de
`workflow_dispatch` manual:

| Workflow | Publica |
| --- | --- |
| `.github/workflows/publish-identity-api-image.yml` | `includeluisferreira/identity-api` |
| `.github/workflows/publish-agent-bridge-image.yml` | `includeluisferreira/agent-bridge` |

Ambos chamam o workflow reutilizável
`.github/workflows/publish-linx-core-image.yml`.

### Matriz de paths

| Caminho alterado | `identity-api` | `agent-bridge` |
| --- | --- | --- |
| `linx_core/services/identity_api/**` | sim | não |
| `linx_core/services/agent_bridge/**` | não | sim |
| `linx_core/shared/**` | sim | sim |
| `linx_core/alembic.ini` | sim | não |
| `.github/workflows/publish-identity-api-image.yml` | sim | não |
| `.github/workflows/publish-agent-bridge-image.yml` | não | sim |
| `.github/workflows/publish-linx-core-image.yml` | sim | sim |
| Demais paths (frontend, docs, routing, middleware etc.) | não | não |

Os filtros `paths` só valem para `push` em branches; pushes de tag não os
avaliam. Por isso os workflows ficam restritos a `develop`/`main` e execução
manual. `workflow_dispatch` ignora os filtros e publica sob demanda.

### Tags

| Origem | Tags |
| --- | --- |
| `develop` | `dev` e `sha-<short-sha>` |
| `main` | `latest` e `sha-<short-sha>` |
| `workflow_dispatch` em `develop` | `dev` e `sha-<short-sha>` |
| `workflow_dispatch` em `main` | `latest` e `sha-<short-sha>` |
| `workflow_dispatch` em outra branch | somente `sha-<short-sha>` |

Um push em `main` não sobrescreve a tag `dev` usada pelo laboratório. As imagens
são construídas para `linux/amd64` e o manifesto publicado é validado com
`docker manifest inspect` ao final do workflow.

### Secrets

Configure em **Settings → Secrets and variables → Actions** do repositório:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN` — token com permissão de escrita nos dois repositórios do
  Docker Hub (os mesmos secrets já usados pelo workflow do tenant app).

O workflow usa `permissions: contents: read` e `concurrency` por serviço para
evitar duas publicações simultâneas da mesma imagem.

## Rollback

Para uma reversão rápida do Deployment, volte ao ReplicaSet anterior:

```bash
kubectl -n linx rollout undo deployment/identity-api
kubectl -n linx rollout undo deployment/agent-bridge
kubectl -n linx rollout status deployment/identity-api
kubectl -n linx rollout history deployment/identity-api
```

Prefira, porém, fixar uma tag imutável `sha-*` ou um digest em um overlay e
reaplicá-lo. Isso é reproduzível e não depende da tag mutável `dev`:

```yaml
images:
  - name: includeluisferreira/identity-api
    newTag: sha-<SHORT_SHA>
  - name: includeluisferreira/agent-bridge
    newTag: sha-<SHORT_SHA>
```

```bash
kubectl apply -k <overlay-de-rollback>
kubectl -n linx rollout status deployment/identity-api
```

Para digest, use o campo `digest` do Kustomize:

```yaml
images:
  - name: includeluisferreira/identity-api
    newName: includeluisferreira/identity-api
    digest: sha256:<DIGEST>
```

## Evidências (Entrega 3 — relatório técnico)

```bash
kubectl -n linx get pods -o wide
# 2x agent-bridge, 2x identity-api, 1x postgres, todos Running (initContainers
# concluídos)

kubectl -n linx get endpoints agent-bridge identity-api
# endpoints não vazios (selector OK)

kubectl -n linx run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup agent-bridge.linx.svc.cluster.local
# resolve para o ClusterIP do Service

kubectl -n linx run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup identity-api.linx.svc.cluster.local

kubectl -n linx port-forward svc/agent-bridge 50051:50051 &
# o servidor não habilita reflection; informe o proto local ao grpcurl:
grpcurl -plaintext -import-path proto -proto linx_agent.proto localhost:50051 list
# lista o serviço linx.AgentBridge do proto/linx_agent.proto

kubectl -n linx port-forward svc/identity-api 8000:8000 &
curl -s http://localhost:8000/health

kubectl -n linx logs deploy/identity-api -c migrate --tail=5
# initContainer migrate aplica "alembic upgrade head"; o advisory lock serializa
# as duas réplicas, então apenas uma execução efetiva aparece
```

## Limpeza / reset do ambiente local

Remove apenas o que esta issue cria. O Secret local e o cluster são descartáveis;
não execute isto contra um cluster compartilhado ou com dados reais.

```bash
# 1. Remove os recursos do namespace e o namespace em si
kubectl delete -k deploy/k8s
kubectl delete namespace linx

# 2. Remove o Secret local (nunca foi versionado; está no .gitignore)
rm -f deploy/k8s/linx-secrets.env

# 3. Opcional: apaga o cluster local e as imagens de desenvolvimento
#    (isto remove o contexto kubectl; para voltar, rode "Criar o cluster local")
k3d cluster delete linx
docker rmi includeluisferreira/identity-api:dev includeluisferreira/agent-bridge:dev
```

Se o namespace ficar preso em `Terminating` (finalizer não concluído porque o
cluster foi parado antes da limpeza), confirme que ele está vazio e force a
finalização **apenas em cluster local descartável**:

```bash
kubectl get ns linx -o json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); d["spec"]["finalizers"]=[]; print(json.dumps(d))' \
  | kubectl replace --raw /api/v1/namespaces/linx/finalize -f -
```

Depois é só repetir o README a partir de **Criar o cluster local (k3d)**:
criar cluster → namespace/Secret → aplicar o kustomize (o cluster puxa as
imagens do Docker Hub). Se estiver em ambiente sem registry, use o fallback
offline.

## Limitações conhecidas

- O caminho padrão depende de acesso ao Docker Hub. O fallback offline com
  `docker save | ctr images import` cobre clusters sem registry, mas exige
  `imagePullPolicy: IfNotPresent` temporário e não é o fluxo normal.
- A tag `dev` é mutável e usada pelo laboratório. Para produção, fixe uma tag
  `sha-*` ou um digest em um overlay; `latest` e `dev` não são referências
  imutáveis.
- `deploy/overlays/ecr` é um exemplo editável com placeholders; não o aplique sem
  substituir `<AWS_ACCOUNT_ID>`, `<AWS_REGION>` e `<SHORT_SHA>`.
- O load balancing de Service ClusterIP é L4 (por conexão); uma conexão gRPC
  longa fica presa a um único pod. Balanceamento por chamada exigiria headless
  service + client-side LB — fora de escopo desta issue.
- O Postgres deste manifest é efêmero (PVC sem `storageClassName`: usa a
  StorageClass padrão do cluster — `local-path` no k3s, `standard` no kind, o
  default em outros ambientes) e existe apenas para sustentar as evidências.
  Dados de produção não pertencem aqui.
- RabbitMQ no cluster é pendência; `RABBITMQ_AMQP_HOST`/`RABBITMQ_MANAGEMENT_URL`
  no ConfigMap são informativos e não bloqueiam os pods desta issue.
