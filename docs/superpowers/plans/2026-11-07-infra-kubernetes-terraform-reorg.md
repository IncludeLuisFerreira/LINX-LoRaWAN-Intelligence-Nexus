# Reorganização dos módulos Kubernetes e Terraform — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover os manifests Kubernetes para `infra/kubernetes/` e o Terraform para `infra/terraform/`, atualizando todas as referências sem quebrar render Kustomize nem validação Terraform.

**Architecture:** Dois módulos vizinhos em `infra/`: `infra/kubernetes/` contém a base Kustomize e seus overlays; `infra/terraform/` contém o módulo K3s atual. Nenhum conteúdo de manifesto muda, apenas caminhos e referências.

**Tech Stack:** Kustomize (`kubectl kustomize`), Terraform 1.x com provider AWS, Git.

**Spec:** `docs/superpowers/specs/2026-11-07-infra-kubernetes-terraform-reorg-design.md`

**Issue:** #272

## Global Constraints

- Não alterar conteúdo de manifests, imagens, probes ou recursos.
- Não mover `deploy/docker-compose*.yml`, `deploy/nginx/`, `deploy/scripts/`, `deploy/.env.example`.
- Não tocar em `.superpowers/` (ignorado pelo git).
- `git add` explícito, arquivo por arquivo; nunca `git add .` ou `git add -A`.
- Commits em português, Conventional Commits, com `(#272)`.
- Nenhum segredo real, `linx-secrets.env` ou estado Terraform pode ser commitado.

## Review Focus

- Overlay Kustomize ainda apontando para `../../k8s` depois do move → render falha.
- `.gitignore` ainda ignorando `deploy/k8s/linx-secrets.env` → segredo local pode ser commitado em `infra/kubernetes/`.
- README e docs com comando antigo → usuário executa caminho inexistente.
- Terraform executado sem `-chdir=infra/terraform` → `main.tf` não encontrado.
- `git mv` de diretório parcial → arquivos ficam duplicados ou somem do índice.

---

## Task 0: Isolar workspace em worktree

**Files:** nenhum arquivo versionado.

**Interfaces:**
- Consumes: issue #272 criada.
- Produces: worktree em `../Lynx-272` na branch `chore/272-infra-reorg`, com design e plano copiados.

- [ ] **Step 1: Confirmar que a branch atual não é usada para esta task**

Run: `git branch --show-current`
Expected: `feat/257-k8s-service-discovery` (branch de outra task) — não commitar nela.

- [ ] **Step 2: Atualizar refs e conferir worktrees existentes**

```bash
git fetch origin
git worktree list
```

Expected: `origin/develop` atualizado; nenhum worktree em `../Lynx-272`.

- [ ] **Step 3: Criar worktree e branch a partir de `origin/develop`**

```bash
git worktree add ../Lynx-272 -b chore/272-infra-reorg origin/develop
```

- [ ] **Step 4: Copiar design e plano para o worktree**

```bash
mkdir -p ../Lynx-272/docs/superpowers/specs ../Lynx-272/docs/superpowers/plans
cp docs/superpowers/specs/2026-11-07-infra-kubernetes-terraform-reorg-design.md \
  ../Lynx-272/docs/superpowers/specs/
cp docs/superpowers/plans/2026-11-07-infra-kubernetes-terraform-reorg.md \
  ../Lynx-272/docs/superpowers/plans/
```

- [ ] **Step 5: Mover a sessão de trabalho para o worktree**

Use a ferramenta de sessão (`tools.opencode.session_move`) apontando para `../Lynx-272`, ou execute os próximos passos com `workdir` em `../Lynx-272`.

- [ ] **Step 6: Commitar design e plano**

```bash
git add docs/superpowers/specs/2026-11-07-infra-kubernetes-terraform-reorg-design.md \
  docs/superpowers/plans/2026-11-07-infra-kubernetes-terraform-reorg.md
git commit -m "docs(infra): adiciona design e plano da reorganização (#272)"
```

---

## Task 1: Mover módulo Terraform para `infra/terraform`

**Files:**
- Move: `infra/k3s-aws-sandbox/main.tf` → `infra/terraform/main.tf`
- Move: `infra/k3s-aws-sandbox/.terraform.lock.hcl` → `infra/terraform/.terraform.lock.hcl`
- Move: `infra/k3s-aws-sandbox/.gitignore` → `infra/terraform/.gitignore`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces: `infra/terraform/` válido; comandos passam a usar `terraform -chdir=infra/terraform`.

- [ ] **Step 1: Mover o diretório preservando histórico**

```bash
git mv infra/k3s-aws-sandbox infra/terraform
```

- [ ] **Step 2: Confirmar conteúdo e ausência do diretório antigo**

Run: `find infra/terraform -maxdepth 1 -type f | sort && test ! -e infra/k3s-aws-sandbox`
Expected: `main.tf`, `.gitignore`, `.terraform.lock.hcl`; segundo comando sem erro.

- [ ] **Step 3: Validar formatação e configuração**

```bash
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
```

Expected: `fmt -check` sem saída; `validate` com `Success! The configuration is valid.`

- [ ] **Step 4: Revisar diff e commitar**

```bash
git add infra/terraform/main.tf infra/terraform/.terraform.lock.hcl infra/terraform/.gitignore
git status --short
git diff --cached --stat
git commit -m "chore(infra): move módulo Terraform para infra/terraform (#272)"
```

Expected: apenas os três arquivos movidos no commit.

---

## Task 2: Mover manifests Kubernetes e overlays

**Files:**
- Move: `deploy/k8s/*` → `infra/kubernetes/base/*` (exceto README e exemplo de secrets, que ficam na raiz)
- Move: `deploy/overlays/dockerhub/` → `infra/kubernetes/overlays/dockerhub/`
- Move: `deploy/overlays/ecr/` → `infra/kubernetes/overlays/ecr/`
- Create: `infra/kubernetes/kustomization.yaml` (raiz, aponta para `base`)
- Modify: `infra/kubernetes/overlays/dockerhub/kustomization.yaml`
- Modify: `infra/kubernetes/overlays/ecr/kustomization.yaml`
- Modify: `.github/workflows/k8s-ci.yml` (adicionado pela #257 após o plano inicial)

**Interfaces:**
- Consumes: nada da Task 1.
- Produces: `infra/kubernetes/` aplicável com `kubectl apply -k infra/kubernetes`; overlays em `infra/kubernetes/overlays/{dockerhub,ecr}`.

- [ ] **Step 1: Mover base e overlays**

```bash
git mv deploy/k8s infra/kubernetes
git mv deploy/overlays infra/kubernetes/overlays
mkdir -p infra/kubernetes/base
for f in namespace.yaml postgres.yaml linx-config.yaml agent-bridge.yaml \
  identity-api.yaml kustomization.yaml; do
  git mv "infra/kubernetes/$f" "infra/kubernetes/base/$f"
done
```

Criar `infra/kubernetes/kustomization.yaml` na raiz:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - base
```

- [ ] **Step 2: Corrigir caminho relativo da base nos dois overlays**

Em `infra/kubernetes/overlays/dockerhub/kustomization.yaml` e
`infra/kubernetes/overlays/ecr/kustomization.yaml`, trocar:

```yaml
resources:
  - ../../k8s
```

por:

```yaml
resources:
  - ../../base
```

- [ ] **Step 3: Confirmar que `deploy/` não tem mais diretórios Kubernetes**

Run: `find deploy -maxdepth 2 -type d | sort`
Expected: sem `deploy/k8s` e sem `deploy/overlays`; `deploy/nginx` e `deploy/scripts` permanecem.

- [ ] **Step 4: Validar render da base e dos overlays**

```bash
kubectl kustomize infra/kubernetes >/tmp/opencode/k8s-base-new.yaml
grep -c '^kind:' /tmp/opencode/k8s-base-new.yaml
kubectl kustomize infra/kubernetes/base >/dev/null
kubectl kustomize infra/kubernetes/overlays/dockerhub >/dev/null
kubectl kustomize infra/kubernetes/overlays/ecr >/dev/null
```

Expected: contagem `9`; base e os dois overlays sem erro.

- [ ] **Step 5: Atualizar paths e comandos do CI de K8s**

Em `.github/workflows/k8s-ci.yml`, trocar todas as ocorrências de
`deploy/k8s` por `infra/kubernetes` e `deploy/overlays` por
`infra/kubernetes/overlays`. Os blocos `paths` devem ficar:

```yaml
      - "infra/kubernetes/**"
      - ".github/workflows/k8s-ci.yml"
```

E os comandos de render:

```yaml
          out="$(kubectl kustomize infra/kubernetes)"
          out="$(kubectl kustomize infra/kubernetes/overlays/dockerhub)"
          out="$(kubectl kustomize infra/kubernetes/overlays/ecr)"
```

- [ ] **Step 6: Commitar move e correção dos overlays**

```bash
git add infra/kubernetes/base/namespace.yaml infra/kubernetes/base/postgres.yaml \
  infra/kubernetes/base/linx-config.yaml infra/kubernetes/base/agent-bridge.yaml \
  infra/kubernetes/base/identity-api.yaml infra/kubernetes/base/kustomization.yaml \
  infra/kubernetes/kustomization.yaml \
  infra/kubernetes/README.md infra/kubernetes/linx-secrets.example.env \
  infra/kubernetes/overlays/dockerhub/kustomization.yaml \
  infra/kubernetes/overlays/ecr/kustomization.yaml \
  .github/workflows/k8s-ci.yml \
  docs/superpowers/specs/2026-11-07-infra-kubernetes-terraform-reorg-design.md \
  docs/superpowers/plans/2026-11-07-infra-kubernetes-terraform-reorg.md
git commit -m "chore(infra): move manifests Kubernetes para infra/kubernetes (#272)"
```

---

## Task 3: Atualizar referências vivas

**Files:**
- Modify: `.gitignore`
- Modify: `infra/kubernetes/README.md`
- Modify: `infra/kubernetes/linx-secrets.example.env`
- Modify: `docs/index.md`
- Modify: `docs/estrutura_de_pastas/estrutura.md`

**Interfaces:**
- Consumes: novos caminhos das Tasks 1 e 2.
- Produces: documentação e ignore apontando para `infra/kubernetes` e `infra/terraform`.

- [ ] **Step 1: Atualizar `.gitignore`**

Trocar:

```gitignore
deploy/k8s/linx-secrets.env
```

por:

```gitignore
infra/kubernetes/linx-secrets.env
```

- [ ] **Step 2: Atualizar caminhos no README do módulo Kubernetes**

```bash
sed -i \
  -e 's|deploy/k8s|infra/kubernetes|g' \
  -e 's|deploy/overlays|infra/kubernetes/overlays|g' \
  -e 's|infra/k3s-aws-sandbox|infra/terraform|g' \
  infra/kubernetes/README.md
```

- [ ] **Step 3: Atualizar caminhos no exemplo de secrets**

```bash
sed -i 's|deploy/k8s|infra/kubernetes|g' infra/kubernetes/linx-secrets.example.env
```

- [ ] **Step 4: Atualizar a descrição de `infra/` em `docs/index.md`**

Na lista de subsistemas, trocar a linha do `infra/` por uma que mencione os
três blocos:

```markdown
- `infra/` — Infraestrutura base: stack ChirpStack v4 dockerizada (Network Server, Gateway Bridge, MQTT, PostgreSQL), manifests Kubernetes em `kubernetes/` e cluster K3s em Terraform em `terraform/`.
```

Na árvore do repositório, substituir o bloco atual do `infra/` por:

```text
├── infra/                  # Infraestrutura base (Compose, Kubernetes e Terraform)
│   ├── docker-compose.yml         # Stack completa ChirpStack v4
│   ├── docker-compose.base.yml    # Base dev: PostgreSQL 15 + Redis 7 + Mosquitto
│   ├── configuration/      # chirpstack, gateway-bridge, mosquitto, postgresql
│   ├── kubernetes/         # Manifestos K8s (kustomize) e overlays
│   └── terraform/          # Cluster K3s na AWS Sandbox
```

- [ ] **Step 5: Atualizar a linha de `infra/` em `docs/estrutura_de_pastas/estrutura.md`**

Substituir o texto da célula do `infra/` por:

```markdown
| **`infra/`** | Orquestração da **infraestrutura base** compartilhada. Contém a stack Docker Compose (ChirpStack, broker MQTT e banco SaaS), os manifests Kubernetes em `kubernetes/` (base Kustomize + overlays `dockerhub`/`ecr`) e o módulo Terraform do cluster K3s em `terraform/`. |
```

- [ ] **Step 6: Verificar referências vivas**

```bash
grep -rn -E 'deploy/k8s|deploy/overlays|infra/k3s-aws-sandbox' \
  .gitignore infra/kubernetes/README.md infra/kubernetes/linx-secrets.example.env \
  docs/index.md docs/estrutura_de_pastas/estrutura.md
```

Expected: sem saída.

- [ ] **Step 7: Commitar**

```bash
git add .gitignore infra/kubernetes/README.md infra/kubernetes/linx-secrets.example.env \
  docs/index.md docs/estrutura_de_pastas/estrutura.md
git commit -m "docs(infra): atualiza referências para infra/kubernetes e infra/terraform (#272)"
```

---

## Task 4: Atualizar documentação histórica e varredura final

**Files:**
- Modify: `docs/superpowers/plans/2026-11-06-k8s-service-discovery.md`
- Modify: `docs/superpowers/plans/2026-11-07-k8s-dockerhub-images.md`
- Modify: `docs/superpowers/specs/2026-11-07-k8s-dockerhub-images-design.md`

**Interfaces:**
- Consumes: novos caminhos das Tasks 1 e 2.
- Produces: zero referências aos caminhos antigos no repositório versionado.

- [ ] **Step 1: Aplicar substituições nos três documentos**

```bash
sed -i \
  -e 's|deploy/k8s|infra/kubernetes|g' \
  -e 's|deploy/overlays|infra/kubernetes/overlays|g' \
  -e 's|infra/k3s-aws-sandbox|infra/terraform|g' \
  docs/superpowers/plans/2026-11-06-k8s-service-discovery.md \
  docs/superpowers/plans/2026-11-07-k8s-dockerhub-images.md \
  docs/superpowers/specs/2026-11-07-k8s-dockerhub-images-design.md

sed -i -E \
  's#infra/kubernetes/(namespace|postgres|linx-config|agent-bridge|identity-api|kustomization)\.yaml#infra/kubernetes/base/\1.yaml#g' \
  docs/superpowers/plans/2026-11-06-k8s-service-discovery.md \
  docs/superpowers/plans/2026-11-07-k8s-dockerhub-images.md \
  docs/superpowers/specs/2026-11-07-k8s-dockerhub-images-design.md

sed -i 's|\.\./\.\./k8s|../../base|g' \
  docs/superpowers/plans/2026-11-07-k8s-dockerhub-images.md
```

- [ ] **Step 2: Varredura global de caminhos antigos**

```bash
grep -rn --exclude-dir=.git --exclude-dir=.superpowers \
  --exclude='2026-11-07-infra-kubernetes-terraform-reorg*' \
  -E 'deploy/k8s|deploy/overlays|infra/k3s-aws-sandbox' .
```

Expected: sem saída. O design e este plano são excluídos porque citam os
caminhos antigos de propósito, como registro da migração.

- [ ] **Step 3: Varredura de caminho relativo antigo do Kustomize**

```bash
grep -rn --exclude-dir=.git --exclude-dir=.superpowers \
  --exclude='2026-11-07-infra-kubernetes-terraform-reorg*' \
  -F '../../k8s' .
```

Expected: sem saída.

- [ ] **Step 4: Revalidar tudo**

```bash
kubectl kustomize infra/kubernetes >/tmp/opencode/k8s-base-final.yaml
grep -c '^kind:' /tmp/opencode/k8s-base-final.yaml
kubectl kustomize infra/kubernetes/base >/dev/null
kubectl kustomize infra/kubernetes/overlays/dockerhub >/dev/null
kubectl kustomize infra/kubernetes/overlays/ecr >/dev/null
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
```

Expected: `9`; overlays sem erro; `fmt -check` sem saída; `validate` com sucesso.

- [ ] **Step 5: Confirmar que nenhum segredo/estado entrou no índice**

```bash
git status --short
git ls-files | grep -E 'linx-secrets\.env$|\.tfstate$|\.terraform/' || true
```

Expected: nenhum `linx-secrets.env` real, nenhum `tfstate`, nenhum `.terraform/`.

- [ ] **Step 6: Commitar**

```bash
git add docs/superpowers/plans/2026-11-06-k8s-service-discovery.md \
  docs/superpowers/plans/2026-11-07-k8s-dockerhub-images.md \
  docs/superpowers/specs/2026-11-07-k8s-dockerhub-images-design.md
git commit -m "docs(infra): atualiza caminhos históricos do Kubernetes e Terraform (#272)"
```

- [ ] **Step 7: Revisão final do branch**

```bash
git log --oneline origin/develop..HEAD
git diff --stat origin/develop...HEAD
```

Expected: commits `docs(infra)`, `chore(infra)` referenciando `#272`; nenhuma alteração fora de `infra/`, `deploy/`, `docs/` e `.gitignore`.

---

## Execução

Método escolhido pelo usuário: **worktree isolado** (`../Lynx-272`, branch `chore/272-infra-reorg`). Não fazer push nem PR sem autorização explícita.
