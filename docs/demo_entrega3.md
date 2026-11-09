# Demo da Entrega 3 — roteiro de terminal

Roteiro para demonstrar, ao vivo, **coordenação, nomeação e consistência/
replicação** no cluster Kubernetes local (k3d) ou no k3s da AWS Sandbox.

Tempo estimado: 12–15 minutos.

> Execute os comandos a partir da raiz do repositório principal, onde os
> `.venv` dos serviços já estão instalados. O worktree de desenvolvimento serve
> apenas para editar os manifests/documentos.

## Pré-requisitos

- `kubectl`, `k3d`, `docker`, `openssl`.
- Cluster k3d `linx` criado (`k3d cluster create linx`) ou k3s da AWS acessível.
- Imagens locais `includeluisferreira/jobs-worker:dev`, ou a imagem publicada
  no registry.
- `bitnamilegacy/postgresql:15` e `rabbitmq:3.13-management-alpine` acessíveis
  (pull automático ou importadas no nó).

## 1. Preparar o cluster local

```bash
k3d cluster start linx
kubectl config use-context k3d-linx

# cluster descartável: remove o namespace antigo (inclusive PVCs/Deployment
# postgres de versões anteriores do manifest)
case "$(kubectl config current-context)" in
  k3d-*) kubectl delete namespace linx --ignore-not-found ;;
  *) echo "contexto não é k3d-*; aborte ou adapte o comando"; exit 1 ;;
esac
```

Importe a imagem do `jobs-worker` (o repositório Docker Hub
`includeluisferreira/jobs-worker` pode não existir no momento da demo) e as
imagens de banco/broker em todos os nós:

```bash
# se a imagem local não existir:
# docker build -t includeluisferreira/jobs-worker:dev \
#   -f linx_core/services/jobs_worker/Dockerfile linx_core

docker pull bitnamilegacy/postgresql:15
docker pull rabbitmq:3.13-management-alpine

for node in $(kubectl get nodes -o jsonpath='{.items[*].metadata.name}'); do
  docker save includeluisferreira/jobs-worker:dev \
    | docker exec -i "$node" ctr -n k8s.io images import -
  docker save bitnamilegacy/postgresql:15 \
    | docker exec -i "$node" ctr -n k8s.io images import -
  docker save rabbitmq:3.13-management-alpine \
    | docker exec -i "$node" ctr -n k8s.io images import -
done
```

## 2. Criar namespace e Secret

```bash
kubectl apply -f infra/kubernetes/base/namespace.yaml

PGPASS=$(openssl rand -hex 16)
REPPASS=$(openssl rand -hex 16)
RABBITPASS=$(openssl rand -hex 16)
SVC=$(openssl rand -hex 32)
AGENT=$(openssl rand -hex 32)
CHIRP=$(openssl rand -hex 16)

kubectl -n linx create secret generic linx-secrets \
  --from-literal=POSTGRES_USER=linxadm \
  --from-literal=POSTGRES_PASSWORD="$PGPASS" \
  --from-literal=POSTGRES_DB=linxdb \
  --from-literal=POSTGRES_REPLICATION_PASSWORD="$REPPASS" \
  --from-literal=DATABASE_URL="postgresql+psycopg://linxadm:$PGPASS@postgres-0.postgres.linx.svc.cluster.local:5432/linxdb" \
  --from-literal=SERVICE_TOKEN="$SVC" \
  --from-literal=AGENT_SERVICE_TOKEN="$AGENT" \
  --from-literal=CHIRPSTACK_API_TOKEN="$CHIRP" \
  --from-literal=RABBITMQ_ADMIN_USER=admin \
  --from-literal=RABBITMQ_ADMIN_PASSWORD="$RABBITPASS" \
  --from-literal=RABBITMQ_TENANT_SECRET="$RABBITPASS" \
  --from-literal=RABBITMQ_AMQP_URL="amqp://admin:$RABBITPASS@rabbitmq.linx.svc.cluster.local:5672/"
```

## 3. Aplicar os manifests

```bash
kubectl apply -k infra/kubernetes

# usar a imagem local do jobs-worker sem tentar o Docker Hub
kubectl -n linx patch deployment jobs-worker --type=strategic -p '{
  "spec":{"template":{"spec":{
    "initContainers":[{"name":"wait-for-db","imagePullPolicy":"IfNotPresent"}],
    "containers":[{"name":"jobs-worker","imagePullPolicy":"IfNotPresent"}]
  }}}
}'

kubectl -n linx wait --for=condition=Ready pod -l app=postgres --timeout=300s
kubectl -n linx rollout status deployment/rabbitmq --timeout=300s
kubectl -n linx rollout status deployment/identity-api --timeout=300s
kubectl -n linx rollout status deployment/agent-bridge --timeout=300s
kubectl -n linx rollout status deployment/jobs-worker --timeout=300s
kubectl -n linx get pods -o wide
```

Resultado esperado: `postgres-0`, `postgres-1`, `rabbitmq`, 2× `identity-api`,
2× `agent-bridge` e 3× `jobs-worker` em `Running`.

## 4. Nomeação e service discovery

```bash
kubectl -n linx get svc,endpoints

kubectl -n linx run dns-test --rm -i --image=busybox:1.36 --restart=Never -- \
  nslookup agent-bridge.linx.svc.cluster.local

kubectl -n linx run dns-test --rm -i --image=busybox:1.36 --restart=Never -- \
  nslookup postgres-0.postgres.linx.svc.cluster.local

kubectl -n linx run dns-test --rm -i --image=busybox:1.36 --restart=Never -- \
  nslookup postgres-1.postgres.linx.svc.cluster.local
```

Fala: “O CoreDNS do Kubernetes resolve cada Service e cada pod do StatefulSet.
Os nomes são estáveis e independentes do IP do pod.”

UUIDv4 dos envelopes:

```bash
grep -n "envelope_id" middleware/services/routing/src/routing/envelope.py
cd middleware/services/routing && .venv/bin/python -m pytest tests/test_envelope.py -q
cd ../../..
```

## 5. Eleição de líder

```bash
kubectl -n linx get pods -l app=jobs-worker -o wide
kubectl -n linx get lease jobs-worker -o jsonpath='{.spec.holderIdentity}{"\n"}'

for p in $(kubectl -n linx get pods -l app=jobs-worker -o name); do
  echo "== $p"
  kubectl -n linx logs "$p" --tail=100 | grep "leader election" || echo "(sem evento)"
done
```

Fala: “O `Lease` tem um único `holderIdentity`. Só a réplica líder registra
`leader election: acquired`; as demais tentam adquirir quando o Lease expira.”

Failover:

```bash
LEADER=$(kubectl -n linx get lease jobs-worker -o jsonpath='{.spec.holderIdentity}')
echo "derrubando líder: $LEADER"
kubectl -n linx delete pod "$LEADER"
timeout 45 kubectl -n linx get lease jobs-worker -w
```

Depois do comando:

```bash
kubectl -n linx get lease jobs-worker -o jsonpath='{.spec.holderIdentity}{"\n"}'

for p in $(kubectl -n linx get pods -l app=jobs-worker -o name); do
  echo "== $p"
  kubectl -n linx logs "$p" --tail=50 | grep "leader election" | tail -3
done
```

## 6. Exclusão mútua (advisory lock)

Em um terminal:

```bash
kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "SELECT pg_try_advisory_lock(927351); SELECT pg_sleep(15);"' &
```

Em outro terminal, durante os 15s:

```bash
kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -Atc "SELECT pg_try_advisory_lock(927351);"'
# esperado: f
```

Fala: “É o mesmo lock usado pelo `alembic upgrade head`: duas réplicas do
`identity-api` não aplicam migrations ao mesmo tempo.”

## 7. Replicação e consistência

```bash
kubectl -n linx get pods -l app=postgres -o wide

kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" -c "SELECT pg_is_in_recovery();"'
# f = primary

kubectl -n linx exec postgres-1 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" -c "SELECT pg_is_in_recovery();"'
# t = replica

kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "SELECT usename, application_name FROM pg_stat_replication;"'
# uma linha: replicator | walreceiver.
# client_addr/replay_lag exigem pg_monitor; a sincronização é provada pelo LSN.
```

Escrita no primary e leitura na réplica:

```bash
kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "CREATE TABLE IF NOT EXISTS demo_replication (id uuid PRIMARY KEY, criado_em timestamptz DEFAULT now());
       INSERT INTO demo_replication (id) VALUES (gen_random_uuid());"'

kubectl -n linx exec postgres-1 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -c "SELECT count(*) FROM demo_replication;"'

# LSN do primary x reproduzido na réplica: pode divergir por ms, então
# espere o replay alcançar o LSN capturado antes de comparar
PRIMARY_LSN=$(kubectl -n linx exec postgres-0 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -Atc "SELECT pg_current_wal_lsn();"')
echo "LSN primary: $PRIMARY_LSN"

until [ "$(kubectl -n linx exec postgres-1 -- sh -c \
  "PGPASSWORD=\"\$POSTGRESQL_PASSWORD\" psql -U \"\$POSTGRESQL_USERNAME\" -d \"\$POSTGRESQL_DATABASE\" \
   -Atc \"SELECT pg_wal_lsn_diff(pg_last_wal_replay_lsn(), '$PRIMARY_LSN') >= 0;\"")" = "t" ]; do
  sleep 1
done

kubectl -n linx exec postgres-1 -- sh -c \
  'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USERNAME" -d "$POSTGRESQL_DATABASE" \
   -Atc "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();"'
```

Fala: “Replicação assíncrona: a réplica aplica o WAL com atraso de
milissegundos. O modelo é eventual na réplica; escrita e read-after-write ficam
no primary. A definição completa está em `docs/consistencia_replicacao.md`.”

## 8. Réplica de serviço

```bash
kubectl -n linx get pods -l app=identity-api
kubectl -n linx delete pod "$(kubectl -n linx get pods -l app=identity-api \
  -o jsonpath='{.items[0].metadata.name}')"

kubectl -n linx run curl-health --rm -i --image=busybox:1.36 --restart=Never -- \
  wget -qO- http://identity-api.linx.svc.cluster.local:8000/health
# {"status":"ok","db":true} — o Service segue atendendo com a outra réplica
```

Fala: “O Service continua atendendo com a segunda réplica enquanto o pod
derrubado é recriado.”

## 9. Testes automatizados

```bash
cd linx_core/shared
.venv/bin/python -m pytest tests/test_leader_election.py tests/test_uuid4.py -q

cd ../services/jobs_worker
.venv/bin/python -m pytest tests/test_leader_gating.py -q

cd ../../../middleware/services/routing
.venv/bin/python -m pytest tests/test_envelope.py -q
```

## Variante AWS Sandbox

Com o cluster k3s provisionado por `infra/terraform` e o Secret aplicado no
master:

```bash
export MASTER_IP=$(cd infra/terraform && terraform output -raw master_public_ip)
alias kx='ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP "KUBECONFIG=/home/ubuntu/.kube/config kubectl"'

kx get pods -n linx
kx get lease jobs-worker -o jsonpath='{.spec.holderIdentity}{"\n"}'
```

O restante dos comandos é idêntico, trocando `kubectl` por `kx`.

> Para a AWS, a imagem `jobs-worker` precisa estar publicada no Docker Hub ou
> importada no nó (`docker save | ssh ... sudo k3s ctr images import -`).

## Limitações a declarar

- Sem failover automático do Postgres; a réplica é somente leitura.
- Sem read/write split no código; todas as escritas vão para `postgres-0`.
- Sem Lamport/Redis lock (#258); exclusão mútua via Postgres.
- RabbitMQ e Postgres do cluster são efêmeros (laboratório).
