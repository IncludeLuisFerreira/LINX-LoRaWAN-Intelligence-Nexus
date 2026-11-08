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
cp ~/Downloads/labsuser.pem ~/Documentos/projetos/reais/Lynx/labsuser.pem
chmod 400 ~/Documentos/projetos/reais/Lynx/labsuser.pem
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
cd ~/Documentos/projetos/reais/Lynx-eks/infra/terraform
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

ssh -i ~/Documentos/projetos/reais/Lynx/labsuser.pem -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl create namespace linx --dry-run=client -o yaml | kubectl apply -f - && \
   kubectl create secret generic linx-secrets -n linx \
     --from-literal=POSTGRES_USER=linxadm \
     --from-literal=POSTGRES_PASSWORD=$SVC_TOKEN \
     --from-literal=POSTGRES_DB=linxdb \
     --from-literal=DATABASE_URL=postgresql+psycopg://linxadm:$SVC_TOKEN@postgres.linx.svc.cluster.local:5432/linxdb \
     --from-literal=SERVICE_TOKEN=$SVC_TOKEN \
     --from-literal=AGENT_SERVICE_TOKEN=$AGENT_TOKEN \
     --from-literal=CHIRPSTACK_API_TOKEN=dev-token \
     --from-literal=RABBITMQ_ADMIN_USER=admin \
     --from-literal=RABBITMQ_ADMIN_PASSWORD=$RABBIT_SECRET \
     --from-literal=RABBITMQ_TENANT_SECRET=$RABBIT_SECRET"
```

Depois aplica os manifests:

```bash
kubectl kustomize ~/Documentos/projetos/reais/Lynx-eks/infra/kubernetes | \
  ssh -i ~/Documentos/projetos/reais/Lynx/labsuser.pem -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
  "KUBECONFIG=/home/ubuntu/.kube/config kubectl apply -f -"
```

---

## 4. Verificar o estado do cluster

```bash
ssh -i ~/Documentos/projetos/reais/Lynx/labsuser.pem -o IdentitiesOnly=yes ubuntu@$MASTER_IP \
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

## 6. Destruir ao terminar (evita gastar créditos)

```bash
cd ~/Documentos/projetos/reais/Lynx-eks/infra/terraform
terraform destroy -var="key_name=vockey" -auto-approve
```

---

## Resumo dos serviços

| Serviço      | Acesso               | Porta                  |
|--------------|----------------------|------------------------|
| identity-api | Internet (NodePort)  | `<MASTER_IP>:30080`    |
| agent-bridge | Interno (ClusterIP)  | —                      |
| postgres     | Interno (ClusterIP)  | —                      |
