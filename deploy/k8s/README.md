# Service Discovery no k3s (issue #257)

Manifestos Kubernetes para expor `agent_bridge` e `identity_api` internamente via
CoreDNS do k3s. Namespace `linx`, aplicação via `kubectl apply -k`.

## Pré-requisitos

- Cluster k3s local (recomendado: `k3d cluster create linx`) **ou** acesso ao
  k3s da sandbox provisionado por `infra/k3s-aws-sandbox`.
- `kubectl` (context apontando para o cluster).
- `grpcurl` (evidência gRPC).
- Imagem `busybox` para o teste de DNS.

## Build das imagens

O Compose só define `build:`, sem nome de imagem. Os manifests esperam as tags
locais abaixo — construa antes do apply:

```bash
docker build -t linx/identity-api:dev -f linx_core/services/identity_api/Dockerfile linx_core
docker build -t linx/agent-bridge:dev  -f linx_core/services/agent_bridge/Dockerfile  linx_core
```

## Import no cluster

- **k3d local:**

  ```bash
  # Não use `k3d image import`: o modo padrão sofre race (k3d#1484) e o
  # --mode=direct pode travar em deadlock no k3d v5.9.0. Importe direto no
  # containerd do nó do cluster:
  SERVER_NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
  docker save linx/identity-api:dev linx/agent-bridge:dev \
    | docker exec -i "$SERVER_NODE" ctr -n k8s.io images import -
  ```

- **sandbox AWS (sem registry no Learner Lab):**

  ```bash
  docker save linx/identity-api:dev linx/agent-bridge:dev | ssh <host> 'sudo k3s ctr images import -'
  ```

## Secret

Nenhum segredo real é commitado. Copie o template, preencha e crie o Secret
antes do apply (os serviços rejeitam placeholder no startup):

```bash
cp deploy/k8s/linx-secrets.example.env deploy/k8s/linx-secrets.env
# editar linx-secrets.env (DATABASE_URL aponta para postgres.linx.svc.cluster.local:5432)
kubectl create secret generic linx-secrets -n linx --from-env-file=deploy/k8s/linx-secrets.env
```

`deploy/k8s/linx-secrets.env` está no `.gitignore` — nunca versionar.

## Apply

```bash
kubectl apply -k deploy/k8s
```

## Evidências (Entrega 3 — relatório técnico)

```bash
kubectl -n linx get pods -o wide
# 2x agent-bridge, 2x identity-api, 1x postgres, todos Running

kubectl -n linx get endpoints agent-bridge identity-api
# endpoints não vazios (selector OK)

kubectl -n linx run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup agent-bridge.linx.svc.cluster.local
# resolve para o ClusterIP do Service

kubectl -n linx run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
  nslookup identity-api.linx.svc.cluster.local

kubectl -n linx port-forward svc/agent-bridge 50051:50051 &
grpcurl -plaintext localhost:50051 list
# lista o serviço AgentBridge do proto/linx_agent.proto

kubectl -n linx port-forward svc/identity-api 8000:8000 &
curl -s http://localhost:8000/health

kubectl -n linx logs deploy/identity-api -c migrate --tail=5
# migrations aplicadas uma única vez por pod (initContainer)
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
k3d cluster delete linx
docker rmi linx/identity-api:dev linx/agent-bridge:dev
```

Se o namespace ficar preso em `Terminating` (finalizer não concluído porque o
cluster foi parado antes da limpeza), confirme que ele está vazio e force a
finalização **apenas em cluster local descartável**:

```bash
kubectl get ns linx -o json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); d["spec"]["finalizers"]=[]; print(json.dumps(d))' \
  | kubectl replace --raw /api/v1/namespaces/linx/finalize -f -
```

Depois é só repetir o fluxo desde o início: criar cluster, buildar imagens,
importar no containerd, recriar o Secret e aplicar o kustomize.

## Limitações conhecidas

- O load balancing de Service ClusterIP é L4 (por conexão); uma conexão gRPC
  longa fica presa a um único pod. Balanceamento por chamada exigiria headless
  service + client-side LB — fora de escopo desta issue.
- O Postgres deste manifest é efêmero (PVC `local-path`) e existe apenas para
  sustentar as evidências. Dados de produção não pertencem aqui.
- RabbitMQ no cluster é pendência; `RABBITMQ_AMQP_HOST`/`RABBITMQ_MANAGEMENT_URL`
  no ConfigMap são informativos e não bloqueiam os pods desta issue.
