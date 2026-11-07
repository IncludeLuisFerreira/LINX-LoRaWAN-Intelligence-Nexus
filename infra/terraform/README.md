# Terraform — Cluster K3s (AWS Sandbox)

## Backend S3 — bootstrap (uma única vez)

O estado do Terraform fica em S3 com lock via DynamoDB. Antes do primeiro
`terraform init`, crie o bucket e a tabela de lock:

```bash
aws s3api create-bucket --bucket linx-k3s-tfstate --region us-east-1
aws s3api put-bucket-versioning --bucket linx-k3s-tfstate \
  --versioning-configuration Status=Enabled
aws dynamodb create-table \
  --table-name linx-k3s-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

> Se `create-bucket` falhar com `BucketAlreadyExists`, troque
> `linx-k3s-tfstate` por um nome globalmente único no comando acima e no bloco
> `backend "s3"` de `main.tf`.

Depois:

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform plan
```

## Uso local (opcional)

O `init` local usa o mesmo backend S3 do CI, então exige credenciais AWS
válidas (as mesmas variáveis `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e
`AWS_SESSION_TOKEN`) e não cria state no diretório. O `plan` é seguro; o
`apply` local disputa o lock do DynamoDB com o CI — nunca rode os dois ao mesmo
tempo:

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply -var="key_name=vockey"
```

O caminho recomendado é o `workflow_dispatch` abaixo; o uso local serve para
inspeção e depuração.

## Apply/destroy via GitHub Actions

O workflow `.github/workflows/terraform.yml` tem dois jobs:

- **Terraform Plan** (`terraform-plan`): roda em push/PR para `develop` e
  `main`; faz `init`, `validate` e `plan`, e comenta o plano no PR. Não aplica.
- **Terraform Apply/Destroy + Deploy** (`orchestration`): roda **somente** em
  `workflow_dispatch`.

Para disparar pela interface: **Actions → "Terraform CI/CD" → Run workflow**,
escolha a branch, a `action` (`apply` ou `destroy`) e o `key_name` (EC2 Key Pair,
default `vockey`). Pela CLI:

```bash
# apply: cria/atualiza a infraestrutura e faz o deploy dos manifests
gh workflow run terraform.yml -f action=apply -f key_name=vockey

# destroy: remove a infraestrutura provisionada pelo Terraform
gh workflow run terraform.yml -f action=destroy -f key_name=vockey
```

O que esperar de cada ação:

- **apply**: `terraform init` + `terraform apply -auto-approve`; em seguida, via
  SSH no master, aguarda o `cloud-init` e os nós ficarem `Ready`, cria o Secret
  `linx-secrets` e aplica os manifests (veja a seção seguinte). Ao final,
  imprime `kubectl get all -A`.
- **destroy**: apenas `terraform init` + `terraform destroy -auto-approve`. Os
  passos de SSH/deploy são ignorados porque o master deixa de existir. O bucket
  `linx-k3s-tfstate` e a tabela de lock **não** são gerenciados pelo Terraform e
  permanecem após o destroy.

O `concurrency: terraform` serializa plan e apply/destroy: uma execução por vez,
sem cancelar a anterior, para proteger o state remoto.

Configuração em **Settings → Secrets and variables → Actions**:

- **Secrets** (aba *Secrets*): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN`, `EC2_SSH_KEY` (conteúdo da chave privada `.pem`) e
  `LINX_SECRETS_ENV` (conteúdo do `linx-secrets.env` real, nunca versionado).
- **Variável de repositório** (aba *Variables*, **não** é secret):
  `TF_VAR_KEY_NAME` com o nome da EC2 Key Pair (ex.: `vockey`). O job
  `terraform-plan` a injeta como `TF_VAR_key_name`; como `variable "key_name"`
  não tem `default` no `main.tf`, sem essa variável o plan fica vermelho em
  push/PR (key pair com nome vazio).

## Deploy dos manifests

O runner do GitHub Actions **não** alcança a API do K3s: a porta 6443 é restrita
ao CIDR da VPC no security group. Por isso o `kubectl` roda no próprio master
via SSH (`ubuntu@<master_public_ip>`), sem baixar kubeconfig e sem alterar
regras de security group.

Depois do `terraform apply`, o job `orchestration` executa:

1. Cria o namespace `linx` de forma idempotente.
2. Cria/atualiza o Secret `linx-secrets` a partir do secret `LINX_SECRETS_ENV`
   do GitHub, entregue por pipe (`--from-env-file=/dev/stdin`) numa única sessão
   SSH. O conteúdo nunca é impresso no log.
3. Aplica os manifests no master: o runner renderiza com
   `kubectl kustomize infra/kubernetes` e envia por pipe para
   `kubectl apply -f -` dentro do master. O efeito é o mesmo de rodar
   `kubectl apply -k infra/kubernetes` na máquina master (fluxo local
   documentado em [`infra/kubernetes/README.md`](../kubernetes/README.md)).

O Secret `linx-secrets` é o mesmo conjunto de chaves de
`infra/kubernetes/linx-secrets.example.env`. Alterou uma credencial? Atualize o
secret `LINX_SECRETS_ENV` no GitHub e rode o workflow com `action=apply`
novamente — o passo do Secret é idempotente.

## Diagnóstico

Obtenha o IP público do master (com o state remoto configurado):

```bash
terraform -chdir=infra/terraform output master_public_ip
terraform -chdir=infra/terraform output -raw ssh_command   # comando SSH pronto
```

Acesse o master e verifique o cluster:

```bash
ssh ubuntu@<master_public_ip>
# se a chave não estiver no ssh-agent: ssh -i ~/.ssh/vockey.pem ubuntu@<ip>

kubectl get nodes
kubectl -n linx get pods
kubectl -n linx get all
```

Valide o `/health` do `identity-api` com `port-forward` **no master** (a API não
é exposta externamente):

```bash
kubectl -n linx port-forward svc/identity-api 8000:8000 &
curl -s http://localhost:8000/health   # {"status":"ok","db":true}
```

`kubectl port-forward` também pode ser aberto a partir da sua máquina com um
túnel SSH, útil quando você não quer manter sessão interativa no master:

```bash
# 1. na sua máquina: abre o túnel e mantém a sessão SSH
ssh -L 8000:localhost:8000 ubuntu@<master_public_ip>

# 2. nessa sessão (no master): sobe o port-forward em background
kubectl -n linx port-forward svc/identity-api 8000:8000 &

# 3. em outro terminal local:
curl -s http://localhost:8000/health
```

Sintomas comuns: pods em `ImagePullBackOff` (registry/Docker Hub inacessível ou
tag inexistente), `CrashLoopBackOff` com erro de variável obrigatória (Secret
`linx-secrets` ausente/desatualizado) e `Pending` por falta de recursos nos nós.
