# Reorganização dos módulos Kubernetes e Terraform em `infra/` (design)

**Data:** 2026-11-07
**Status:** aguardando aprovação
**Issue:** a definir antes da execução (proposta: nova issue `chore(infra)`; não reutilizar #257, que é service discovery)

## Intenção e por quê

Hoje os manifests Kubernetes ficam em `deploy/k8s/` e o Terraform fica em
`infra/k3s-aws-sandbox/`. São dois módulos de infraestrutura que deveriam ser
vizinhos, porque o próximo objetivo é o Terraform aplicar os manifests no
cluster que provisiona. A distância atual obriga caminhos relativos frágeis
(`../../k8s`) e esconde a dependência entre cluster e carga de trabalho.

Objetivo: deixar os dois módulos lado a lado dentro de `infra/`, sem quebrar
nenhum comando ou referência ativa.

## Goals

- Mover os manifests de `deploy/k8s/` para `infra/kubernetes/`.
- Mover os overlays de `deploy/overlays/` para `infra/kubernetes/overlays/`.
- Mover o Terraform de `infra/k3s-aws-sandbox/` para `infra/terraform/`.
- Atualizar todas as referências a caminhos antigos, incluindo planos e specs
  históricos em `docs/superpowers/` (decisão explícita do usuário).
- Preservar `kubectl kustomize` / `kubectl apply -k` funcionando.
- Preservar `terraform validate` funcionando.

## Non-goals

- Fazer o Terraform aplicar os manifests. Isso é o próximo objetivo e vira
  issue própria.
- Alterar conteúdo dos manifests, imagens, probes ou recursos.
- Alterar o fluxo Docker Compose em `deploy/` e `infra/`.
- Criar pipeline CI novo para K8s.

## Anti-goals

- Deixar qualquer referência ativa a `deploy/k8s`, `deploy/overlays` ou
  `infra/k3s-aws-sandbox`.
- Commitar `linx-secrets.env` ou estado Terraform.
- Esconder quebra de caminho em documentação histórica.

## Abordagens consideradas

1. **`infra/kubernetes` + `infra/terraform`, overlays junto dos manifests** —
   escolhida. Simetria entre os dois módulos e caminho relativo simples para o
   próximo passo (`../kubernetes`).
2. **Só mover Kubernetes, manter Terraform em `infra/k3s-aws-sandbox`** —
   menor diff, mas mantém assimetria e não atende “reorganizar os dois módulos”.
3. **`infra/kubernetes` + `infra/terraform/k3s-aws-sandbox`** — prepara vários
   módulos Terraform, mas adiciona um nível que hoje não tem uso.

## Estrutura final

```text
infra/
├── kubernetes/
│   ├── README.md
│   ├── namespace.yaml
│   ├── postgres.yaml
│   ├── linx-config.yaml
│   ├── agent-bridge.yaml
│   ├── identity-api.yaml
│   ├── kustomization.yaml
│   ├── linx-secrets.example.env
│   └── overlays/
│       ├── dockerhub/kustomization.yaml
│       └── ecr/kustomization.yaml
└── terraform/
    ├── main.tf
    ├── .terraform.lock.hcl
    └── .gitignore
```

`deploy/k8s/` e `deploy/overlays/` deixam de existir. `deploy/` continua com o
Compose, nginx e scripts que não pertencem a Kubernetes.

## Movimentos de arquivo

| Origem | Destino |
| --- | --- |
| `deploy/k8s/*` (6 YAML + README + exemplo de secrets) | `infra/kubernetes/` |
| `deploy/overlays/dockerhub/` | `infra/kubernetes/overlays/dockerhub/` |
| `deploy/overlays/ecr/` | `infra/kubernetes/overlays/ecr/` |
| `infra/k3s-aws-sandbox/main.tf` | `infra/terraform/main.tf` |
| `infra/k3s-aws-sandbox/.terraform.lock.hcl` | `infra/terraform/.terraform.lock.hcl` |
| `infra/k3s-aws-sandbox/.gitignore` | `infra/terraform/.gitignore` |

## Referências a atualizar

Arquivos vivos:

- `.gitignore`: `deploy/k8s/linx-secrets.env` → `infra/kubernetes/linx-secrets.env`.
- `infra/kubernetes/README.md`: todos os comandos e exemplos (`deploy/k8s` →
  `infra/kubernetes`, `deploy/overlays` → `infra/kubernetes/overlays`,
  `infra/k3s-aws-sandbox` → `infra/terraform`).
- `infra/kubernetes/linx-secrets.example.env`: comentários de caminho.
- `infra/kubernetes/overlays/dockerhub/kustomization.yaml`: `../../k8s` → `../..`.
- `infra/kubernetes/overlays/ecr/kustomization.yaml`: `../../k8s` → `../..`.
- `docs/estrutura_de_pastas/estrutura.md` e `docs/index.md`: descrever
  `infra/kubernetes` e `infra/terraform` na árvore de pastas.

Documentação histórica (decisão do usuário: atualizar tudo):

- `docs/superpowers/plans/2026-11-06-k8s-service-discovery.md`
- `docs/superpowers/plans/2026-11-07-k8s-dockerhub-images.md`
- `docs/superpowers/specs/2026-11-07-k8s-dockerhub-images-design.md`

`.superpowers/` está no `.gitignore`; não versionar nem editar como entrega.

## Validação

Antes do move (baseline já executado):

- `kubectl kustomize deploy/k8s` renderiza 9 recursos.
- `kubectl kustomize deploy/overlays/dockerhub` e `.../ecr` passam.
- `terraform -chdir=infra/k3s-aws-sandbox validate` passa.

Depois do move:

- `kubectl kustomize infra/kubernetes` renderiza os mesmos 9 recursos.
- `kubectl kustomize infra/kubernetes/overlays/dockerhub` e `.../ecr` passam.
- `terraform -chdir=infra/terraform fmt -check` e `terraform validate` passam.
- `grep -rn` por `deploy/k8s`, `deploy/overlays`, `infra/k3s-aws-sandbox` sem
  resultados fora de `.git/` (exceto menções históricas que decidirmos manter;
  a meta é zerar).
- `git diff --stat` revisado para garantir que só arquivos do escopo entraram.

## Riscos e mitigação

- **Kustomize quebrar por path relativo:** validar os três diretórios depois do
  move.
- **Documentação com caminho velho:** grep global antes do commit.
- **Terraform perder estado local:** estado/`.terraform/` não estão no git;
  mover apenas arquivos versionados e avisar que plan/apply usam
  `-chdir=infra/terraform`.
- **Conflito com trabalho de outro agente:** a branch atual é
  `feat/257-k8s-service-discovery`; executar em branch própria da nova issue.

## Fora de escopo / próximo passo

Integrar Terraform e manifests (`kubernetes_manifest`, `kubectl apply` em
`local-exec`, ou pipeline separado) fica para uma issue seguinte, depois que a
reorganização estiver mergeada.
