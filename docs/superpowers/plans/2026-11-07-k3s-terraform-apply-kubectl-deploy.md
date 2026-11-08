# Pipeline de apply do Terraform e deploy Kubernetes via GitHub Actions — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar apply/destroy do cluster K3s no CI com estado durável (backend S3 + lock DynamoDB) e automatizar o deploy dos manifests via SSH no master, num único `workflow_dispatch`.

**Architecture:** O Terraform passa a usar backend remoto S3 (com lock DynamoDB), eliminando a causa do estado órfão que a #276 contornou. O `.github/workflows/terraform.yml` ganha um job de orquestração acionado por `workflow_dispatch` que faz `apply`/`destroy` e, no `apply`, aguarda readiness (`cloud-init status --wait` + `kubectl wait`) e aplica os manifests rodando `kubectl` no master via SSH (o runner não alcança a API 6443, restrita à VPC).

**Tech Stack:** Terraform 1.9 (provider AWS ~> 5.0, backend S3), DynamoDB (lock), GitHub Actions, Kustomize (`kubectl kustomize`), SSH.

**Spec:** `docs/superpowers/specs/2026-11-07-k3s-terraform-apply-kubectl-deploy-design.md`

**Issue:** #278

> **Emenda (2026-11-07, execução):** o Learner Lab nega `dynamodb:CreateTable`
> ao papel `voclabs`. O backend usa **lock nativo do S3** (`use_lockfile = true`,
> Terraform >= 1.10, pinado em 1.17.1 no CI), sem tabela DynamoDB. Tarefas que
> citam DynamoDB devem ser lidas com essa substituição.

## Global Constraints

- Backend S3 hardcodado no `main.tf` (bucket `linx-k3s-tfstate`, key `terraform.tfstate`, região `us-east-1`, tabela `linx-k3s-tfstate-lock`) — bucket precisa ser globalmente único; ajustar no bootstrap.
- A porta 6443 permanece restrita à VPC (`10.0.0.0/16`); **não** abrir para o público e **não** reescrever o `server` do kubeconfig para IP público.
- `kubectl` roda **no master via SSH** (usuário `ubuntu`, AMI jammy 22.04), nunca no runner contra a API.
- Readiness por `cloud-init status --wait` + `kubectl wait`, **sem** loop de `sleep`.
- Secret `linx-secrets` criado numa **única sessão SSH** lendo `$LINX_SECRETS_ENV` de `/dev/stdin` (`echo "$LINX_SECRETS_ENV" | ssh ...`); nunca expor o conteúdo em log aberto nem em arquivo temporário.
- Nunca commitar `tfstate`/`tfplan`/`linx-secrets.env`/chave privada (`.gitignore` de `infra/terraform` já cobre).
- Deploy consome imagens Docker Hub `:dev` da base (`kubectl apply -k infra/kubernetes`); não publicar imagens (escopo #257).
- `git add` explícito, arquivo por arquivo; nunca `git add .`/`git add -A`/`git commit -a`.
- Commits em português, Conventional Commits, com `(#278)`.
- Sem push/PR sem autorização explícita após validação real.

## Review Focus

- Bucket/tabela não existirem no `terraform init` → init falha logo no primeiro job. (Task 1 bootstrap; Task 4 runbook.)
- `LINX_SECRETS_ENV` vazar em log se o runner rodar com `set -x` → entregar via pipe único para `/dev/stdin` (nunca `echo` solto para o log nem arquivo temporário). (Task 3.)
- `kubectl wait` expirar porque os workers nunca ficam `Ready` (join falhou) → comando tem `--timeout=120s` e o job falha explicitamente, sem falso verde. (Task 3 + Task 5.)
- Secret `linx-secrets` ausente ou com placeholder `change-me` → pods em CrashLoopBackOff. (Task 3 cria o Secret antes do apply; Task 5 valida chaves reais.)
- Nome de bucket colidir (já em uso global) → bootstrap ajusta para nome único antes de qualquer commit. (Task 1.)

---

## Task 0: Isolar workspace em worktree

**Files:** nenhum arquivo versionado.

**Interfaces:**
- Consumes: issue #278 criada; design aprovado.
- Produces: worktree `../Lynx-278` na branch `feat/278-terraform-apply-kubectl-deploy`, com design e plano copiados.

- [ ] **Step 1: Confirmar que a branch atual não é desta task**

Run: `git branch --show-current`
Expected: `feat/tarraform-yml` (task #276, alheia) — não commitar nela.

- [ ] **Step 2: Atualizar refs e conferir worktrees**

```bash
git fetch origin
git worktree list
```

Expected: `origin/develop` atualizado; nenhum worktree `../Lynx-278`.

- [ ] **Step 3: Criar worktree e branch a partir de `origin/develop`**

```bash
git worktree add ../Lynx-278 -b feat/278-terraform-apply-kubectl-deploy origin/develop
```

- [ ] **Step 4: Copiar design e plano para o worktree**

```bash
mkdir -p ../Lynx-278/docs/superpowers/specs ../Lynx-278/docs/superpowers/plans
cp docs/superpowers/specs/2026-11-07-k3s-terraform-apply-kubectl-deploy-design.md \
  ../Lynx-278/docs/superpowers/specs/
cp docs/superpowers/plans/2026-11-07-k3s-terraform-apply-kubectl-deploy.md \
  ../Lynx-278/docs/superpowers/plans/
```

- [ ] **Step 5: Mover a sessão de trabalho para o worktree**

Use `tools.opencode.session_move` apontando para `../Lynx-278`, ou execute os próximos passos com `workdir` em `../Lynx-278`.

- [ ] **Step 6: Commitar design e plano**

```bash
git add docs/superpowers/specs/2026-11-07-k3s-terraform-apply-kubectl-deploy-design.md \
  docs/superpowers/plans/2026-11-07-k3s-terraform-apply-kubectl-deploy.md
git commit -m "docs(infra): adiciona design e plano do apply/deploy Kubernetes (#278)"
```

---

## Task 1: Backend S3 + DynamoDB no `main.tf`

**Files:**
- Modify: `infra/terraform/main.tf` (bloco `terraform { ... }`, linhas 6-20)

**Interfaces:**
- Consumes: nada (worktree isolado).
- Produces: `main.tf` com `backend "s3"`; `terraform validate` continua passando sem init do backend; nomes do bucket/tabela fixados para as Tasks 3-4.

- [ ] **Step 1: Substituir o bloco backend local por S3**

No `infra/terraform/main.tf`, dentro de `terraform { ... }` (hoje só comentário "Backend local por padrão"), adicionar:

```hcl
  backend "s3" {
    bucket         = "linx-k3s-tfstate"          # ajustar para nome globalmente único
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "linx-k3s-tfstate-lock"
  }
```

Manter `required_version = ">= 1.3.0"` e `required_providers` intactos. Remover/atualizar o comentário "Backend local" para não contradizer o código.

- [ ] **Step 2: Validar formatação e sintaxe sem init do backend**

```bash
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
```

Expected: `fmt -check` sem saída; `validate` com `Success! The configuration is valid.` (o `validate` não exige o bucket existir).

- [ ] **Step 3: Registrar o comando de bootstrap no rascunho do runbook**

Criar `infra/terraform/README.md` com a seção "Backend S3 — bootstrap (uma única vez)" contendo exatamente:

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

Anotar no README: trocar `linx-k3s-tfstate` por um nome globalmente único se `create-bucket` falhar com `BucketAlreadyExists`.

- [ ] **Step 4: Commitar**

```bash
git add infra/terraform/main.tf infra/terraform/README.md
git commit -m "feat(infra): usa backend S3 com lock DynamoDB no Terraform (#278)"
```

---

## Task 2: Investigar SSM + OIDC no Learner Lab (gate de decisão)

**Files:**
- Modify: `infra/terraform/README.md` (registrar o resultado da decisão)

**Interfaces:**
- Consumes: nada.
- Produces: decisão documentada — **mecanismo de execução remota** (`ssh` vs `aws ssm send-command`) e **mecanismo de credenciais** (`AWS_*` temporários vs OIDC). A Task 3 lê esta decisão.

- [ ] **Step 1: Testar credenciais via OIDC do GitHub Actions**

Tentar, no contexto do Learner Lab, criar um provedor OIDC e role de assumable role, ou consultar se o perfil `voclabs` permite `iam:CreateOpenIDConnectProvider` e `iam:CreateRole`.

Run: `aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com 2>&1 | head`

Expected: registrar o erro real (`AccessDenied`/`NotAuthorized` ou sucesso). Learner Lab normalmente **bloqueia** (IAM restrito).

- [ ] **Step 2: Testar execução remota via SSM**

Tentar listar instâncias gerenciadas pelo SSM:

Run: `aws ssm describe-instance-information 2>&1 | head`

Expected: se `AccessDeniedException` ou lista vazia (instâncias sem SSM agent/instance profile), SSM **não** é viável sem criar instance profile (que o lab bloqueia).

- [ ] **Step 3: Registrar a decisão no README**

No `infra/terraform/README.md`, gravar uma seção "Mecanismo de execução remota" com a conclusão:

- Se SSM **e** OIDC forem permitidos → adotar `aws ssm send-command` + OIDC (sem porta 22, sem `.pem`, sem renovação manual).
- Caso contrário (esperado) → oficializar o fallback **SSH + tokens temporários**, que é o caminho implementado na Task 3.

- [ ] **Step 4: Commitar**

```bash
git add infra/terraform/README.md
git commit -m "docs(infra): registra decisão sobre SSM/OIDC vs SSH (#278)"
```

---

## Task 3: Redesenhar `terraform.yml` (apply/destroy + deploy via SSH)

> **Pré-condição:** decisão da Task 2. Se a Task 2 concluiu "SSM + OIDC permitidos", aplicar as substituições do Step 8 **antes** de commitar. Caso contrário (fallback esperado), implementar exatamente o fluxo SSH abaixo.

**Files:**
- Modify: `.github/workflows/terraform.yml` (todo o arquivo)

**Interfaces:**
- Consumes: backend S3 (Task 1); decisão SSM/OIDC (Task 2).
- Produces: workflow com trigger `workflow_dispatch` (inputs `action` e `key_name`), `concurrency: group terraform`, job `terraform-plan` (mantido) e job `orchestration` (apply/destroy + deploy). Secrets consumidos: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `EC2_SSH_KEY`, `LINX_SECRETS_ENV`; var `TF_VAR_KEY_NAME`.

- [ ] **Step 1: Adicionar trigger `workflow_dispatch` e `concurrency`**

No topo do `terraform.yml`, manter os triggers atuais (`push`/`pull_request` para develop/main) e adicionar:

```yaml
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

- [ ] **Step 2: Manter o job `terraform-plan` intacto**

O job `terraform-plan` atual (plan em PR/push, com comentário no PR) continua sem mudança de passos. Só passa a herdar o backend S3 no `terraform init`.

- [ ] **Step 3: Criar o job `orchestration` (apply/destroy)**

Job `orchestration`, `runs-on: ubuntu-latest`, `if: github.event_name == 'workflow_dispatch'`, `defaults.run.working-directory: infra/terraform`, e `env` com:

```yaml
    env:
      AWS_REGION: "us-east-1"
      LINX_SECRETS_ENV: ${{ secrets.LINX_SECRETS_ENV }}
```

Passos 1-3 (comuns):

```yaml
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9.0"
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-session-token: ${{ secrets.AWS_SESSION_TOKEN }}
          aws-region: us-east-1
```

- [ ] **Step 4: Adicionar `terraform init` e `apply`/`destroy`**

```yaml
      - name: Terraform Init
        run: terraform init
      - name: Terraform Apply ou Destroy
        run: |
          terraform ${{ github.event.inputs.action }} \
            -var="key_name=${{ github.event.inputs.key_name }}" \
            -auto-approve
```

- [ ] **Step 5: Adicionar steps condicionais de SSH (apenas `apply`)**

Com `if: ${{ github.event.inputs.action == 'apply' }}`:

1. Configurar chave privada: `echo "${{ secrets.EC2_SSH_KEY }}" > ~/.ssh/id_rsa && chmod 600 ~/.ssh/id_rsa` (o valor é mascarado pelo GitHub; redirecionado ao arquivo, sem imprimir).
2. Obter IP: `MASTER_IP=$(terraform output -raw master_public_ip)` e `echo "MASTER_IP=${MASTER_IP}" >> $GITHUB_ENV`.
3. `ssh-keyscan -H $MASTER_IP >> ~/.ssh/known_hosts`.

- [ ] **Step 6: Adicionar step de readiness (sem retry cego)**

Com `if: apply`, um único step:

```yaml
      - name: Aguardar readiness do cluster
        if: ${{ github.event.inputs.action == 'apply' }}
        run: |
          ssh ubuntu@${{ env.MASTER_IP }} \
            "cloud-init status --wait && kubectl wait --for=condition=Ready nodes --all --timeout=120s"
```

Expected: retorna `0` só quando o cloud-init terminou **e** todos os nós estão `Ready`; senão o job falha.

- [ ] **Step 7: Adicionar step de deploy (secret + manifests, sessão SSH única)**

Com `if: apply`:

```yaml
      - name: Deploy dos manifests (kubectl no master via SSH)
        if: ${{ github.event.inputs.action == 'apply' }}
        run: |
          echo "$LINX_SECRETS_ENV" | ssh ubuntu@${{ env.MASTER_IP }} "
            kubectl create namespace linx --dry-run=client -o yaml | kubectl apply -f - &&
            kubectl create secret generic linx-secrets -n linx \
              --from-env-file=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
          "
          kubectl kustomize infra/kubernetes | ssh ubuntu@${{ env.MASTER_IP }} "kubectl apply -f -"
          ssh ubuntu@${{ env.MASTER_IP }} "kubectl get all -A"
```

Nota: `$LINX_SECRETS_ENV` vem de `env` (mapa `env` do job), não de `echo` no corpo; o pipe para `/dev/stdin` evita expor o conteúdo em `set -x`.

- [ ] **Step 8 (condicional): substituições se SSM/OIDC forem permitidos**

Aplicar **somente** se a Task 2 aprovou: trocar o `configure-aws-credentials` para `role-to-assume` (OIDC), remover os steps de chave SSH, e substituir cada `ssh ubuntu@$MASTER_IP "..."` por `aws ssm send-command --instance-ids <master> --document-name "AWS-RunShellScript" --parameters commands='["..."]'`. Manter `kubectl kustomize` no runner, mas o `kubectl apply` continua no master (via SSM).

- [ ] **Step 9: Commitar**

```bash
git add .github/workflows/terraform.yml
git commit -m "ci(infra): adiciona apply/destroy e deploy via SSH no terraform.yml (#278)"
```

---

## Task 4: Runbook e documentação

**Files:**
- Modify: `infra/terraform/README.md` (completar com uso local/CI e destroy)
- Create: `docs/devops/k3s-aws-ci-cd.md` (ponteiro curto para o runbook)

**Interfaces:**
- Consumes: nomes do backend (Task 1), fluxo do workflow (Task 3).
- Produces: runbook completo que o operador segue para bootstrap, apply, destroy e diagnóstico.

- [ ] **Step 1: Completar o runbook em `infra/terraform/README.md`**

Seções mínimas:

- "Backend S3 — bootstrap" (já na Task 1).
- "Apply/destroy via GitHub Actions": como disparar `workflow_dispatch` (`action` apply/destroy, `key_name`), e o que esperar de cada job.
- "Deploy dos manifests": explicar que o `kubectl apply -k infra/kubernetes` roda no master via SSH e que o Secret `linx-secrets` vem de `LINX_SECRETS_ENV`.
- "Diagnóstico": `terraform output master_public_ip`, `ssh ubuntu@<ip>`, `kubectl get nodes`, `kubectl -n linx get pods`, e como validar `/health` via `kubectl port-forward`.

- [ ] **Step 2: Criar `docs/devops/k3s-aws-ci-cd.md`**

Um parágrafo resumindo o fluxo (backend S3, workflow_dispatch apply/destroy, deploy via SSH) com link para `infra/terraform/README.md` e para a spec #278.

- [ ] **Step 3: Commitar**

```bash
git add infra/terraform/README.md docs/devops/k3s-aws-ci-cd.md
git commit -m "docs(infra): runbook do apply/destroy e deploy Kubernetes (#278)"
```

---

## Task 5: Validação end-to-end e PR

**Files:** nenhum código novo; validação no lab + PR.

**Interfaces:**
- Consumes: tudo das Tasks 1-4.
- Produces: evidência de apply/destroy real e PR #278 descrita.

- [ ] **Step 1: Rodar o bootstrap no lab (uma vez)**

Executar os comandos do runbook (bucket + versioning + tabela) com credenciais válidas do Learner Lab. Se o bucket já existir, ajustar para nome único e refletir no `main.tf`.

- [ ] **Step 2: Destruir resíduo de apply local anterior**

Se houver cluster vivo de apply local anterior, destruí-lo manualmente (`terraform destroy` local) para "começar do zero", conforme spec.

- [ ] **Step 3: Validar localmente antes do dispatch**

```bash
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
kubectl kustomize infra/kubernetes >/dev/null
```

Expected: sem saída de `fmt`; `validate` com sucesso; `kubectl kustomize` sem erro.

- [ ] **Step 4: Disparar `workflow_dispatch` com `action: apply`**

Via `gh workflow run terraform.yml -f action=apply -f key_name=vockey` (ou botão no GitHub). Acompanhar o run.

Expected: job `orchestration` verde; `kubectl get all -A` mostra `identity-api`/`agent-bridge`/`postgres` `Running`; `/health` responde `{"status":"ok","db":true}` via `kubectl port-forward`.

- [ ] **Step 5: Disparar `workflow_dispatch` com `action: destroy`**

Expected: job verde; `terraform output` vazio após; novo `apply` recria do zero (prova de estado durável).

- [ ] **Step 6: Abrir PR de #278**

Push da branch `feat/278-terraform-apply-kubectl-deploy` e abrir PR para `develop`. Descrever: o que foi feito, arquivos alterados, resultados reais dos Steps 4-5, o que o CI **não** cobre (apply/destroy só por `workflow_dispatch`), e pendências. Sem merge automático.

---

## Execução

Método a definir com o usuário (subagent-driven ou native). Não fazer push/PR sem autorização explícita e sem os resultados reais dos Steps 4-5 registrados.
