# Terraform — Cluster K3s (AWS)

## Backend S3 — bootstrap (uma única vez)

O estado do Terraform fica em S3 com **lock nativo do próprio bucket**
(`use_lockfile = true`, Terraform >= 1.10). Antes do primeiro `terraform init`,
crie o bucket versionado:

```bash
aws s3api create-bucket --bucket linx-k3s-tfstate --region us-east-2 \
  --create-bucket-configuration LocationConstraint=us-east-2
aws s3api put-bucket-versioning --bucket linx-k3s-tfstate \
  --versioning-configuration Status=Enabled
```

> O lock via DynamoDB **não é usado**: o Learner Lab nega `dynamodb:CreateTable`
> para o papel `voclabs`. O `use_lockfile` grava o lock num objeto
> `terraform.tfstate.tflock` no S3 e não exige DynamoDB.

> Se `create-bucket` falhar com `BucketAlreadyExists`, troque
> `linx-k3s-tfstate` por um nome globalmente único no comando acima e no bloco
> `backend "s3"` de `main.tf`.

Depois:

```bash
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform plan
```

## Conta real — teste rápido com state local

Para uma demonstração pontual sem criar o bucket S3, use o backend local
(`-backend=false`) e restrinja SSH/NodePort ao seu IP:

```bash
aws login --profile linx-dev
export AWS_PROFILE=linx-dev

MY_IP=$(curl -s https://checkip.amazonaws.com)

ssh-keygen -t ed25519 -f ~/.ssh/linx-k3s-real.pem -N ""
aws ec2 import-key-pair --key-name linx-k3s-real \
  --public-key-material fileb://$HOME/.ssh/linx-k3s-real.pem.pub

terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform apply \
  -var="key_name=linx-k3s-real" \
  -var="ssh_cidr=${MY_IP}/32"
```

O state fica em `infra/terraform/terraform.tfstate` (gitignored). Para destruir:

```bash
terraform -chdir=infra/terraform destroy \
  -var="key_name=linx-k3s-real" \
  -var="ssh_cidr=${MY_IP}/32"
```

> O `ssh_command` de output aponta para `~/.ssh/<key_name>.pem`.
> A chave pública é importada; a privada fica só na sua máquina.

## Uso local (opcional)

O `init` local usa o mesmo backend S3 do CI, então exige credenciais AWS
válidas (as mesmas variáveis `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e
`AWS_SESSION_TOKEN`) e não cria state no diretório. O `plan` é seguro; o
`apply` local disputa o lock nativo do S3 com o CI — nunca rode os dois ao mesmo
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

## Migração do state local → S3 (uma única vez)

Se o cluster foi criado **antes** do backend S3, o state está apenas em
`infra/terraform/terraform.tfstate` (local). Migre-o antes do primeiro `apply`
no CI — com o S3 vazio, o CI não enxergaria os recursos e tentaria criar um
segundo cluster:

```bash
cd infra/terraform
cp /caminho/do/state/antigo/terraform.tfstate .
terraform init -migrate-state   # confirme "yes" para copiar o state ao S3
terraform plan                  # esperado: "No changes"
```

Se o `init -migrate-state` não oferecer a cópia (diretório sem backend anterior
registrado), envie o state manualmente:

```bash
cd infra/terraform
terraform init
terraform state push terraform.tfstate
terraform plan
```

Depois da migração, a fonte de verdade é o S3. O arquivo local pode ser
removido. O `plan` deve sair sem mudanças; uma eventual diferença de IP público
é normal se as instâncias estiverem paradas.

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
gh workflow run terraform.yml --ref develop -f action=apply -f key_name=vockey

# destroy: remove a infraestrutura provisionada pelo Terraform
gh workflow run terraform.yml --ref develop -f action=destroy -f key_name=vockey
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
  não tem `default` no `main.tf`, sem essa variável o plan falha em push/PR com
  o erro `No value for required variable` (variável `key_name` sem default).

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

As imagens referenciadas são as tags `:dev` do Docker Hub (base
`infra/kubernetes`) — informação útil ao depurar `ImagePullBackOff` (tag
inexistente ou registry inacessível).

O Secret `linx-secrets` é o mesmo conjunto de chaves de
`infra/kubernetes/linx-secrets.example.env`. Alterou uma credencial? Atualize o
secret `LINX_SECRETS_ENV` no GitHub e rode o workflow com `action=apply`
novamente — o passo do Secret é idempotente.

## Diagnóstico

Se `terraform init` (local ou no CI) falhar com `403 Forbidden`/`AccessDenied`
citando a policy `voc-cancel-cred`, a **sessão do Learner Lab foi encerrada**:
a conta e os recursos continuam existindo, mas as credenciais daquela sessão
são negadas. Inicie uma nova sessão no AWS Academy e atualize
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN` no ambiente
local e nos secrets do GitHub. O passo "Diagnóstico — identidade AWS" do job de
plan imprime apenas o número da conta, útil para confirmar que o CI está na
mesma conta do bucket.

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

Saudável: `{"status":"ok","db":true}`. Degradada —
`{"status":"degraded","db":false}` — indica problema no Secret `linx-secrets`
ou no acesso ao banco.

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
