# Runbook — K3s na AWS Sandbox

## Pré-requisitos (uma vez só)

- Terraform instalado (`terraform -version`)
- kubectl instalado (`kubectl version --client`)
- AWS CLI instalado

---

## 1. Toda vez que iniciar uma sessão no Learner Lab

A sessão expira (~4h) e as credenciais mudam. Faça isso sempre ao abrir o lab:

**a) Baixar a chave PEM atualizada:**
1. Acesse o Learner Lab no navegador
2. Clique em **"AWS Details"**
3. Clique em **"Download PEM"**
4. Execute:
```bash
# Salve o PEM em um diretório de sua escolha e ajuste PEM_PATH abaixo
PEM_PATH=~/labsuser.pem
cp ~/Downloads/labsuser.pem "$PEM_PATH"
chmod 400 "$PEM_PATH"
```

**b) Exportar as credenciais AWS:**

Na mesma tela "AWS Details", copie as credenciais e exporte no terminal:
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```

---

## 2. Subir o cluster

```bash
cd infra/terraform
terraform init
terraform apply -var="key_name=vockey" -auto-approve
```

Aguarda ~3 minutos. Ao final, o output mostra o IP do master.

---

## 3. Criar o Secret e aplicar os manifests

> O Secret precisa ser criado **antes** dos pods subirem. As credenciais do
> Secret devem ser únicas — o app rejeita valores padrão como `linx:linx`.

```bash
MASTER_IP=$(terraform output -raw master_public_ip)

SVC_TOKEN=$(openssl rand -hex 32)
AGENT_TOKEN=$(openssl rand -hex 32)
RABBIT_SECRET=$(openssl rand -hex 16)

ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl create namespace linx --dry-run=client -o yaml | kubectl apply -f - && \
   kubectl create secret generic linx-secrets -n linx \
     --from-literal=POSTGRES_USER=linxadm \
     --from-literal=POSTGRES_PASSWORD=$SVC_TOKEN \
     --from-literal=POSTGRES_DB=linxdb \
     --from-literal=DATABASE_URL=postgresql+psycopg://linxadm:$SVC_TOKEN@postgres-0.postgres.linx.svc.cluster.local:5432/linxdb \
     --from-literal=POSTGRES_REPLICATION_PASSWORD=$RABBIT_SECRET \
     --from-literal=SERVICE_TOKEN=$SVC_TOKEN \
     --from-literal=AGENT_SERVICE_TOKEN=$AGENT_TOKEN \
     --from-literal=CHIRPSTACK_API_TOKEN=<seu-chirpstack-api-token> \
     --from-literal=RABBITMQ_ADMIN_USER=admin \
     --from-literal=RABBITMQ_ADMIN_PASSWORD=$RABBIT_SECRET \
     --from-literal=RABBITMQ_TENANT_SECRET=$RABBIT_SECRET \
     --from-literal=RABBITMQ_AMQP_URL=amqp://admin:$RABBIT_SECRET@rabbitmq.linx.svc.cluster.local:5672/ "
```

Depois aplica os manifests (a partir da raiz do repositório):

```bash
kubectl kustomize infra/kubernetes/overlays/nodeport | \
  ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl apply -f -"
```

---

## 4. Verificar o estado do cluster

```bash
ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl get pods -n linx"
```

Aguarda todos os pods ficarem `Running`. O postgres sobe primeiro, depois os outros.

---

## 5. Testar o serviço

```bash
curl http://$MASTER_IP:30080/health
```

Resposta esperada: `{"status":"ok","db":true}`

Docs da API: `http://$MASTER_IP:30080/docs`

---

## 6. Evidência de replicação de dados (Entrega 3)

Confirma que os dois pods do StatefulSet estão no ar:

```bash
ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl get pods -n linx -l app=postgres"
```

Esperado: `postgres-0` (primary) e `postgres-1` (replica) ambos `Running`.

Lê a tabela de migrations no **primary**:

```bash
ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl exec -n linx postgres-0 -- \
   psql -U linxadm -d linxdb -c 'SELECT * FROM alembic_version;'"
```

Lê a mesma tabela na **replica** (dado replicado via WAL):

```bash
ssh -i "$PEM_PATH" -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl exec -n linx postgres-1 -- \
   psql -U linxadm -d linxdb -c 'SELECT * FROM alembic_version;'"
```

Ambos devem retornar a mesma versão do Alembic — prova de replicação em tempo real.

---

## 7. Destruir ao terminar (evita gastar créditos)

```bash
cd infra/terraform
terraform destroy -var="key_name=vockey" -auto-approve
```

---

## Resumo dos serviços

| Serviço      | Acesso               | Porta                  |
|--------------|----------------------|------------------------|
| identity-api | Internet (NodePort)  | `<MASTER_IP>:30080`    |
| agent-bridge | Interno (ClusterIP)  | —                      |
| postgres     | Interno (ClusterIP)  | —                      |
