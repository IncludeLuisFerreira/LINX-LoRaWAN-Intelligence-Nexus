# Pipeline de apply do Terraform e deploy Kubernetes via GitHub Actions — Design

**Data:** 2026-11-07
**Status:** aprovado
**Issue:** #278

## 1. Intenção e porquê

A spec #272 terminou a reorganização de `infra/` e registrou explicitamente o
"próximo passo": integrar o ciclo de vida do cluster K3s com o ciclo dos
manifests Kubernetes. Hoje esse passo não existe:

- O Terraform roda **localmente** (`terraform -chdir=infra/terraform apply`).
  A issue #276 removeu o apply do CI de propósito: com backend **local**, o
  estado morre junto com o runner efêmero e os recursos ficam órfãos — `destroy`
  fica impossível.
- O deploy dos manifests (`kubectl apply -k infra/kubernetes`) é manual, exige
  extrair o kubeconfig do master por SSH e reescrever o `server`.

O PRD proposto pelo usuário descreve exatamente essa automação (terraform apply
+ extração de kubeconfig + kubectl apply num pipeline só), mas assume um
backend local e caminhos/estrutura que o repo já superou.

**Objetivo deste design:** habilitar o apply/destroy no CI de forma segura
(estado durável) e completar a esteira `apply → kubeconfig → kubectl apply`,
corrigindo os pontos em que o PRD conflita com o estado atual do repo.

## 2. Diagnóstico verificado

- `infra/terraform/main.tf` já provisiona VPC `10.0.0.0/16`, SG (SSH 22, K3s API
  6443, NodePort 30000–32767), EC2 master `t3.medium` + workers `t3.small`, K3s
  via cloud-init. O `user_data` do master copia `/etc/rancher/k3s/k3s.yaml` para
  `/home/ubuntu/.kube/config` (aponta para `127.0.0.1`, correto **no** master).
- O SG restringe a porta 6443 ao CIDR da VPC (`10.0.0.0/16`). O runner do
  GitHub (internet pública) **não** alcança a API pelo IP público — logo o
  `kubectl` precisa rodar **no próprio master**, via SSH (não há download de
  kubeconfig nem reescrita de `server` para IP público).
- `infra/terraform/main.tf` usa **backend local** (linha 19) — raiz do problema
  de estado que a #276 contornou removendo o apply.
- Há `terraform.tfstate`/`tfplan` locais não rastreados (apply local já rodou).
  Decisão: **começar do zero** — nada de cluster vivo a preservar; destruir
  qualquer resíduo manualmente antes do primeiro apply no CI.
- `.github/workflows/terraform.yml` (#276) faz **só plan** em PR/push.
- `.github/workflows/k8s-ci.yml` só valida o render do Kustomize; não aplica.
- `infra/kubernetes/base/` usa `secretRef: linx-secrets` em `identity-api` e
  `agent-bridge`, mas o Secret **não está no git** — é criado imperativamente de
  `linx-secrets.example.env`. Logo, `kubectl apply -k` sozinho **não** deixa os
  pods de pé (falta o Secret). O PRD não cobre isso.
- PRD usa `./terraform` e `./kubernetes` (caminhos antigos) e YAMLs numerados
  chatos; o repo usa `infra/terraform` e `infra/kubernetes` com Kustomize
  `base/` + `overlays/`.

## 3. Objetivos

1. Introduzir **backend remoto S3** + **lock DynamoDB** para o estado do
   Terraform durar entre execuções no CI (e local).
2. Reverter a decisão #276: adicionar `workflow_dispatch` com `apply`/`destroy`
   no `.github/workflows/terraform.yml`.
3. No `apply`, encadear: extrair kubeconfig via SSH (reescrevendo `server`) →
   criar o Secret `linx-secrets` → `kubectl apply -k infra/kubernetes`.
4. No `destroy`, remover tudo sem deixar órfão (estado no S3).
5. Documentar o bootstrap único do bucket/tabela (runbook).

## 4. Não-objetivos

- Trocar Kustomize por Helm.
- Provisionar ingress, TLS, RDS, EKS ou RabbitMQ gerenciado.
- Migrar a stack ChirpStack do Compose para Kubernetes.
- Publicar imagens Docker Hub (escopo da #257); o deploy **consome** as imagens
  `:dev` já publicadas da base.
- Expor o serviço externamente (NodePort/LoadBalancer/ingress). Aceitação é
  "pods Running + `/health` interno".
- Criar esteira com aprovação manual, SBOM ou assinatura.

## 5. Anti-objetivos

- Commitar `tfstate`, `tfplan`, `linx-secrets.env` ou chave privada.
- Hardcodar credenciais ou o `k3s_token` em output/log.
- Rodar `apply` no CI sem backend remoto (seria regressão da #276).
- Quebrar o `terraform validate`/`plan` atual ou o render do Kustomize.

## 6. Abordagens consideradas

1. **S3 + DynamoDB + apply no CI** — escolhida. Único caminho que entrega o
   "zero intervenção manual" do PRD mantendo estado durável e `destroy` viável.
2. **Apply local + CI só kubeconfig/kubectl** — respeita a #276, mas mantém o
   provisionamento manual e não atende o objetivo primário do PRD.
3. **Só documentar o fluxo manual** — zero código, não automatiza nada.

**Decisão:** abordagem 1, com a ressalva de que reverte a #276; a reversão é
justificada porque a causa do problema (backend local) passa a ser eliminada
pelo backend remoto, não contornada.

## 7. Arquitetura

### 7.1 Backend S3 + DynamoDB

No `main.tf`, substituir o backend local por:

```hcl
terraform {
  backend "s3" {
    bucket         = "linx-k3s-tfstate"          # nome globalmente único — ajustar
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "linx-k3s-tfstate-lock"
  }
  # required_version / required_providers inalterados
}
```

- Bucket com **versioning** habilitado (recuperação de estado).
- Tabela DynamoDB: PK `LockID` (String), billing `PAY_PER_REQUEST`, para
  serializar `apply` concorrente.

Decisão de design (chamada minha): valores **hardcodados** no bloco, em vez de
`-backend-config`. É um único Learner Lab com um único bucket; hardcodar mantém
local e CI idênticos (só `terraform init`) e evita variável a mais. O nome do
bucket precisa ser trocado por um globalmente único na implementação.

### 7.2 Bootstrap (uma única vez, manual)

Bucket e tabela são pré-requisitos do `terraform init` (Terraform não cria o
próprio backend). Documentar no runbook:

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

Premissa a validar no lab: o perfil voclabs do Learner Lab precisa ter
permissão para S3 e DynamoDB (esperado — não é serviço gerenciado bloqueado
como EKS). Se bloquear, cair para a abordagem 2.

Antes do primeiro `apply` no CI: **começar do zero** — se houver cluster vivo
de um apply local anterior, destruí-lo manualmente (os recursos não estão no
S3). Depois disso, o S3 vazio vira a fonte de verdade.

### 7.3 Workflow redesenhado (`terraform.yml`)

Manter o job `terraform-plan` atual (validação em PR/push para develop/main).
Ele passa a exigir o backend S3 — logo o bootstrap (§7.2) precisa rodar **antes**
do merge para `develop`.

Adicionar trigger e job de orquestração:

```yaml
on:
  workflow_dispatch:
    inputs:
      action:
        description: 'Ação do Terraform'
        required: true
        default: 'apply'
        type: choice
        options: [apply, destroy]
      key_name:
        description: 'EC2 Key Pair na AWS'
        required: true
        default: 'vockey'

concurrency:
  group: terraform
  cancel-in-progress: false
```

Fluxo do job (runs-on ubuntu-latest):

1. Checkout + `setup-terraform` + `configure-aws-credentials` (com
   `AWS_SESSION_TOKEN`, como já existe).
2. `terraform init` (agora com backend S3).
3. `terraform apply`/`destroy` com `-auto-approve -var="key_name=..."`.
4. Se `apply`: configurar `EC2_SSH_KEY`, `ssh-keyscan`, obter
   `master_public_ip` de `terraform output`.
5. **Readiness, não retry cego:** aguardar o cloud-init concluir e os nós
   ficarem `Ready` com timeout explícito:

   ```bash
   ssh ubuntu@$MASTER_IP \
     "cloud-init status --wait && kubectl wait --for=condition=Ready nodes --all --timeout=120s"
   ```

   (dispensa loop de `sleep`; o `cloud-init status --wait` bloqueia até a
   inicialização terminar e o `kubectl wait` até o cluster responder.)
6. **Deploy via SSH (kubectl no master):** o runner não alcança a API (SG 6443
   restrito à VPC), então os comandos `kubectl` rodam no master por stdin. A
   criação do namespace e do Secret consolida-se numa **única sessão SSH**, com
   o `LINX_SECRETS_ENV` lido de `/dev/stdin` (evita múltiplos handshakes e o
   vazamento das credenciais caso o runner rode com `set -x`):

   ```bash
   echo "$LINX_SECRETS_ENV" | ssh ubuntu@$MASTER_IP "
     kubectl create namespace linx --dry-run=client -o yaml | kubectl apply -f - &&
     kubectl create secret generic linx-secrets -n linx \
       --from-env-file=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
   "
   # manifests
   kubectl kustomize infra/kubernetes | ssh ubuntu@$MASTER_IP "kubectl apply -f -"
   # status
   ssh ubuntu@$MASTER_IP "kubectl get all -A"
   ```

`kubectl` e `kubectl kustomize` rodam no runner (`ubuntu-latest` tem `kubectl`).
O master já tem `kubectl` + kubeconfig localhost correto via `user_data`.

### 7.4 Secrets e variáveis

| Nome | Tipo | Origem | Uso |
| --- | --- | --- | --- |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | secret | existente | credenciais temporárias do lab |
| `EC2_SSH_KEY` | secret (novo) | conteúdo da chave privada `.pem` | SSH no master |
| `LINX_SECRETS_ENV` | secret (novo) | conteúdo do `linx-secrets.env` real | cria o Secret `linx-secrets` no cluster |
| `TF_VAR_KEY_NAME` | var | existente | nome da key pair |
| `AWS_REGION` | var | existente (`us-east-1`) | região |

Decisão de design (chamada minha): transportar o `linx-secrets.env` inteiro num
único secret do GitHub (`LINX_SECRETS_ENV`) em vez de um secret por chave —
menos atrito e espelha o fluxo documentado no `linx-secrets.example.env`.

### 7.5 Acesso ao cluster (deploy via SSH)

O runner **não** baixa kubeconfig: o `kubectl` roda no master, que já tem o
`/home/ubuntu/.kube/config` apontando para `127.0.0.1` (correto localmente). A
porta 6443 continua restrita à VPC — nenhuma regra de SG muda. Usuário SSH:
`ubuntu` (AMI jammy 22.04). `ssh-keyscan -H` alimenta o `known_hosts` para o
retry não falhar na primeira execução.

### 7.6 Pré-investigação: SSM + OIDC (antes de codificar)

A solução base deste spec usa **chave SSH** (`EC2_SSH_KEY`) + **tokens
temporários** (`AWS_SESSION_TOKEN`). Antes de codificar, o plano inclui uma
tarefa de investigação para testar, no Learner Lab, duas alternativas com menos
atrito e maior segurança:

1. **AWS Systems Manager (`aws ssm send-command`)** — executa comandos no master
   **sem** abrir a porta 22 nem carregar chave `.pem`. Substitui os passos SSH
   de readiness e deploy se o IAM do lab permitir.
2. **OIDC do GitHub Actions** (`aws-actions/configure-aws-credentials` com
   `role-to-assume` + trust OIDC) — dispensa renovação manual de credenciais
   temporárias. Substitui os secrets `AWS_ACCESS_KEY_ID`/`SECRET`/`SESSION_TOKEN`.

Regra de decisão: se o IAM do Learner Lab permitir, **adotar SSM + OIDC** e o
fluxo SSH/`.pem`/tokens manuais deixa de existir. Se bloquear, o fluxo descrito
neste spec (SSH + tokens) fica **oficializado como fallback necessário** —
exatamente como documentado aqui.

## 8. Mudanças por arquivo

| Arquivo | Mudança |
| --- | --- |
| `infra/terraform/main.tf` | Trocar backend local por `backend "s3"` (bloco). |
| `.github/workflows/terraform.yml` | Adicionar `workflow_dispatch` (apply/destroy), `concurrency`, job de orquestração com passos SSH/secret/kubectl no master. |
| `infra/terraform/README.md` (novo) | Runbook: bootstrap do bucket/tabela, uso local e via CI, `destroy`. |
| `docs/devops/` (ou `infra/README.md`) | Referenciar o novo fluxo apply+deploy. |
| `docs/superpowers/specs/` + `plans/` | Este design + plano de implementação. |

`infra/terraform/.gitignore` já cobre `*.tfstate`, `*.tfstate.*`, `*.tfplan` —
nada a mudar.

## 9. Validação

- `terraform -chdir=infra/terraform fmt -check` e `validate` passam.
- Job `terraform-plan` continua verde em PR (após bootstrap).
- `workflow_dispatch` `apply`: sobe VPC+EC2+K3s; `kubectl get nodes` no master
  mostra master+workers `Ready`; `kubectl -n linx get pods` mostra
  `identity-api`/`agent-bridge`/`postgres` `Running`; `/health` do `identity-api`
  responde `{"status":"ok","db":true}` via `kubectl port-forward` (critério
  interno — sem exposição externa).
- `workflow_dispatch` `destroy`: remove tudo; `terraform output` vazio após;
  nova execução de `apply` recria do zero (prova de estado durável).
- Executar duas vezes seguidas `apply` para confirmar idempotência com o lock.

## 10. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Expiração do `AWS_SESSION_TOKEN` no meio do job | Atualizar secrets antes do disparo; mitigado por OIDC se §7.6 aprovar. |
| S3/DynamoDB bloqueados no Learner Lab | Premissa validada no início; fallback = abordagem 2. |
| Bucket name já em uso | Ajustar para nome único no bootstrap. |
| K3s ainda inicializando ao rodar kubectl | `cloud-init status --wait` + `kubectl wait --for=condition=Ready` (não retry cego). |
| Imagens `:dev` do Docker Hub ausentes (`agent-bridge:dev`) → `ImagePullBackOff` | Dependência da #257; confirmar publicação antes da validação. |
| Secret `linx-secrets` ausente → CrashLoopBackOff | Step 7.3.6 cria o Secret antes do apply; README valida chaves. |
| Runner não alcança API 6443 | kubectl roda no master via SSH; SG inalterado. |
| Chave SSH / `.pem` como vetor de vazamento | `EC2_SSH_KEY` como secret; nunca `echo`; SSM (§7.6) elimina a chave se permitido. |
| Apply concorrente no CI | `concurrency: group terraform` + lock DynamoDB. |
| Cluster vivo de apply local anterior duplicando gasto | "Começar do zero": destruir manual antes do 1º apply no CI. |

## 11. Tracking

- Branch própria a partir de `develop` atualizado (ex.:
  `feat/278-terraform-apply-kubectl-deploy`), issue **#278**.
- A branch atual `feat/tarraform-yml` (task #276) **não** recebe este trabalho;
  a #276 já está fechada; este design substitui o apply que ela removeu.
- Commits em português, Conventional Commits, com o número da issue.

## 12. O que fica para o plano de implementação

O plano deve quebrar o trabalho em tarefas verificáveis: (0) investigar
SSM + OIDC no Learner Lab e decidir o mecanismo de execução remota/credenciais
(§7.6); (1) backend S3 no `main.tf` + bootstrap documentado; (2) workflow
`apply`/`destroy` com readiness por `cloud-init status --wait` + `kubectl wait`
e deploy via SSH numa única sessão (secret + kubectl no master); (3) runbook e
docs; (4) validação local (fmt/validate, render Kustomize) antes de disparar no
lab. Sem commit antes de validação real.
