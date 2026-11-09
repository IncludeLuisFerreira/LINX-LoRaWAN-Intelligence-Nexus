# Evidências na AWS — Entrega 3

Coleta feita em **2026-11-09** na conta AWS do projeto (plano FREE),
região **`us-east-2`**.

## Cluster

| Item | Valor |
| --- | --- |
| Kubernetes | k3s `v1.37.2+k3s1` |
| Nós | 1 master + 2 workers `t3.small` (fora do free tier; cluster efêmero) |
| Master | público `<master_public_ip>`, privado `<master_private_ip>` |
| Workers | privados `<worker_1_private_ip>` e `<worker_2_private_ip>` |
| VPC / SG | `<vpc_id>` / `<sg_id>` |
| Key pair | `linx-k3s-real` |
| Imagem `jobs-worker` | importada nos 3 nós via `k3s ctr images import` (não publicada no Docker Hub) |

```text
NAME              STATUS   ROLES           AGE   VERSION
<master_node>     Ready    control-plane   3m    v1.37.2+k3s1
<worker_node_1>   Ready    <none>          8s    v1.37.2+k3s1
<worker_node_2>   Ready    <none>          9s    v1.37.2+k3s1
```

## Nomeação / DNS interno

```text
agent-bridge.linx.svc.cluster.local  -> 10.43.140.210
postgres-0.postgres.linx.svc.cluster.local -> 10.42.1.7
postgres-1.postgres.linx.svc.cluster.local -> 10.42.0.12
```

## Replicação

```text
postgres-0: pg_is_in_recovery() = f
postgres-1: pg_is_in_recovery() = t
pg_stat_replication: replicator | walreceiver
LSN primary: 0/3039480
LSN replica: 0/3039480 | 0/3039480
```

## Eleição de líder

```text
holder antes: jobs-worker-5d8cbdb8b8-t69s4
holder depois: jobs-worker-5d8cbdb8b8-wpx7p   (sucessão em ~2s)
log do novo líder: leader election: acquired
```

## Réplica de serviço

```text
GET http://<master_public_ip>:30080/health  -> 200 {"status":"ok","db":true}
# pod identity-api-5b6cddc445-mqzzr deletado
# novo pod identity-api-5b6cddc445-r89pn recriado; o outro continuou Running
GET http://<master_public_ip>:30080/health  -> 200 {"status":"ok","db":true}
```

## Comandos de reprodução

```bash
# 1. infraestrutura (conta real, state S3)
terraform -chdir=infra/terraform apply \
  -var="key_name=linx-k3s-real" \
  -var="ssh_cidr=$(curl -s https://checkip.amazonaws.com)/32"

# 2. kubeconfig fica em /home/ubuntu/.kube/config no master
ssh -i ~/.ssh/linx-k3s-real.pem ubuntu@<master_ip>

# 3. secret + manifests (a partir da raiz do repo)
kubectl kustomize infra/kubernetes/overlays/nodeport | \
  ssh -i ~/.ssh/linx-k3s-real.pem ubuntu@<master_ip> \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl apply -f -"
```

## Observações

- O cluster da apresentação é efêmero: destruir com `terraform destroy` após a
  demo para evitar custo.
- O bucket S3 `linx-k3s-tfstate` guarda o state e não é gerenciado pelo
  Terraform.
- O `jobs-worker` precisa da imagem importada ou publicada; o Docker Hub ainda
  não tem `includeluisferreira/jobs-worker`.
- O Postgres/RabbitMQ do laboratório são efêmeros (sem PVC para o RabbitMQ).
