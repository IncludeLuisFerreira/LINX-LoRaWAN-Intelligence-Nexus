# Deploy k8s com imagens do Docker Hub — Design

**Data:** 2026-11-07
**Issue:** #257 — https://github.com/IncludeLuisFerreira/LINX-LoRaWAN-Intelligence-Nexus/issues/257
**Status:** aguardando aprovação

## 1. Intenção e porquê

Hoje o `infra/kubernetes` depende de imagens construídas localmente e importadas
diretamente no containerd do cluster (`docker save | ctr images import`). Isso
funciona apenas em um cluster local e cria atrito para usar o mesmo deployment
na AWS ou em outra empresa.

O objetivo é que `identity-api` e `agent-bridge` sejam consumidos a partir de
imagens públicas no Docker Hub, sem import local, e que o mesmo conjunto de
manifestos possa ser apontado para outro registry (ECR, GHCR, registry privado)
sem reescrever os manifests.

Além disso, o deployment precisa deixar de entrar em loop de migrations quando
o banco ainda não está pronto ou quando a configuração está incompleta, e precisa
conectar de forma confiável ao Postgres dentro do cluster.

## 2. Diagnóstico verificado

- A imagem `includeluisferreira/identity-api:dev` existe no Docker Hub, é
  pública e foi publicada em `linux/amd64`.
- No cluster `kind-linx`, o pod `linx-api` está em `CrashLoopBackOff`.
  Log: `sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from given
  URL string` seguido do retry do `docker-entrypoint.sh`.
- O Deployment usado no teste não tem `envFrom` nem `env`; o Secret `linx-env`
  existe em arquivo, mas não foi aplicado no cluster.
- O Secret de teste aponta `DATABASE_URL` para `db:5432`; no `infra/kubernetes` o
  Service do Postgres se chama `postgres`.
- O `infra/kubernetes/base/identity-api.yaml` usa `linx/identity-api:dev` e o
  `agent-bridge.yaml` usa `linx/agent-bridge:dev`, ambos com import local.
- O initContainer de migration roda em cada réplica (`replicas: 2`), sem lock,
  criando risco de duas migrations concorrentes.
- O `docker-entrypoint.sh` faz até 30 tentativas de `alembic upgrade head`,
  sem distinguir banco indisponível de URL inválida. Uma configuração errada
  vira loop de 90 segundos antes de falhar.
- O PVC do Postgres é `ReadWriteOnce` e o Deployment usa a estratégia padrão
  `RollingUpdate`; isso pode causar conflito de volume durante atualizações.

## 3. Objetivos

1. Publicar `identity-api` e `agent-bridge` no Docker Hub de forma reproduzível.
2. Fazer os manifests puxarem as imagens do Docker Hub por padrão.
3. Permitir trocar o registry sem editar os manifests de base.
4. Injetar corretamente `DATABASE_URL`, `POSTGRES_*` e demais segredos no
   `identity-api` e no `agent-bridge`.
5. Fazer o `identity-api` esperar o Postgres e aplicar migrations uma única vez,
   mesmo com múltiplas réplicas.
6. Fazer o workflow de publicação rodar apenas quando os arquivos daquela
   imagem mudarem.
7. Manter o caminho de import local documentado como fallback, não como padrão.

## 4. Não-objetivos

- Publicar `jobs_worker`, `docker_provisioner`, `routing`, `telemetry_consumer`
  ou frontend nesta issue.
- Trocar Kustomize por Helm.
- Provisionar RDS, EKS, ingress, TLS ou RabbitMQ gerenciado.
- Criar uma esteira completa de release com aprovação manual, SBOM ou assinatura
  de imagem.
- Substituir o Postgres efêmero do laboratório por um banco de produção.

## 5. Anti-objetivos

- Não manter `imagePullPolicy: IfNotPresent` com a tag mutável `dev`: isso pode
  reutilizar uma imagem antiga no nó e mascarar uma publicação nova.
- Não usar `latest` como única referência de produção; releases devem ter tag
  imutável ou digest.
- Não rodar `alembic upgrade head` em loop infinito.
- Não commitar `linx-secrets.env` nem credenciais de registry.
- Não deixar o workflow publicar imagens em qualquer push de arquivo irrelevante.

## 6. Abordagens consideradas

### A — Kustomize base + overlays + GitHub Actions (escolhida)

Base com manifests portáveis e imagens públicas do Docker Hub. Overlays alteram
registry, tag e `imagePullSecrets`. Workflows separados por serviço, com filtros
de caminho. Migration em initContainer com espera pelo banco e lock no Alembic.

**Prós:** portátil, reproduzível, atende AWS e outras empresas, mantém Kustomize.
**Contras:** mais arquivos, exige configurar secrets de Docker Hub no GitHub.

### B — Correção mínima no manifesto atual

Trocar as imagens, adicionar `envFrom`, corrigir `DATABASE_URL` e publicar
`agent-bridge` manualmente.

**Prós:** entrega rápida.
**Contras:** continua dependente de build/push manual, tags mutáveis e pouco
portátil para outro registry.

### C — Helm chart

Chart com `values.yaml` para registry, tags, secrets e banco.

**Prós:** padrão de mercado.
**Contras:** overkill para dois serviços; o repositório já usa Kustomize.

**Decisão:** A, com a exigência do usuário de que o workflow só publique quando
os arquivos da imagem correspondente mudarem.

## 7. Arquitetura proposta

### 7.1 Imagens e registry

Repositórios públicos no Docker Hub:

| Serviço | Imagem |
| --- | --- |
| `identity-api` | `includeluisferreira/identity-api` |
| `agent-bridge` | `includeluisferreira/agent-bridge` |

Tags publicadas:

- `dev`: tag mutável usada pelo laboratório, publicada **somente a partir de
  `develop`**.
- `latest`: publicada **somente a partir de `main`**, para consumo simples.
- `sha-<short-sha>`: tag imutável para rollback e produção, publicada em ambos
  os branches.

A base usa as imagens do Docker Hub e `imagePullPolicy: Always`, porque `dev` é
mutável. Para produção, o overlay deve fixar uma tag `sha-*` ou um digest e pode
usar `IfNotPresent`.

### 7.2 Estrutura Kustomize

Manter os arquivos atuais como base para não quebrar `kubectl apply -k infra/kubernetes`:

```text
infra/kubernetes/
  kustomization.yaml          # raiz: aponta para base/
  linx-secrets.example.env
  README.md
  base/
    kustomization.yaml        # base
    namespace.yaml
    postgres.yaml
    linx-config.yaml
    identity-api.yaml         # imagem Docker Hub, envFrom, probes
    agent-bridge.yaml         # imagem Docker Hub, envFrom
  overlays/
    dockerhub/kustomization.yaml   # explícito para o laboratório
    ecr/kustomization.yaml         # exemplo para AWS/empresa
```

- A base referencia `includeluisferreira/identity-api:dev` e
  `includeluisferreira/agent-bridge:dev`.
- `infra/kubernetes/overlays/dockerhub` apenas referencia a base, servindo de comando
  explícito.
- `infra/kubernetes/overlays/ecr` é um **exemplo editável**, não um overlay aplicável sem
  configuração: Kustomize não interpola variáveis de ambiente. Ele contém
  placeholders explícitos (`<AWS_ACCOUNT_ID>`, `<AWS_REGION>`) e instruções no
  README para o operador copiar/editar ou usar `kustomize edit set image`.
  O patch opcional de `imagePullSecrets` fica comentado.
- O `README.md` passa a documentar `kubectl apply -k infra/kubernetes` como padrão e o
  fluxo de cópia/edição do overlay ECR como caminho AWS/empresa. O overlay de
  exemplo não entra na validação automática de `--dry-run`.

### 7.3 Banco e segredos

- `postgres.yaml` continua existindo para o laboratório, com
  `strategy: Recreate` por causa do PVC `ReadWriteOnce`.
- O Secret `linx-secrets` continua sendo criado imperativamente a partir de
  `linx-secrets.example.env`.
- `DATABASE_URL` aponta para
  `postgresql+psycopg://<user>:<pass>@postgres.linx.svc.cluster.local:5432/<db>`
  no laboratório.
- Em produção, o mesmo Secret aponta para o banco externo (RDS, Cloud SQL etc.);
  nenhum manifesto precisa mudar.
- `identity-api` e `agent-bridge` recebem `envFrom` do ConfigMap e do Secret.
- As chaves mínimas do Secret passam a ser validadas no README:
  `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
  `SERVICE_TOKEN`, `AGENT_SERVICE_TOKEN`, `CHIRPSTACK_API_TOKEN`,
  `RABBITMQ_ADMIN_USER`, `RABBITMQ_ADMIN_PASSWORD`, `RABBITMQ_TENANT_SECRET`.

### 7.4 Migrations

Fluxo do `identity-api`:

1. InitContainer `wait-for-db` aguarda o Postgres aceitar conexões, com timeout
   e mensagem clara. Não há retry de migration em caso de erro de configuração.
2. InitContainer `migrate` executa `alembic upgrade head` uma vez.
3. O `migrations/env.py` adquire um advisory lock do PostgreSQL antes de aplicar
   migrations e libera no `finally`. Com duas réplicas, a segunda espera a
   primeira terminar em vez de disputar a tabela `alembic_version`.
4. O container principal só sobe o `uvicorn` depois que os initContainers
   concluem.

O `docker-entrypoint.sh` continua sendo o caminho do Compose. O k8s não usa o
entrypoint no container principal; o initContainer de migration usa o comando
explícito do Alembic.

O `wait-for-db` será um utilitário compartilhado em
`linx_core/shared/src/linx_shared/db/wait.py`, usado por `identity-api` e
`agent-bridge`. Ele valida a URL, tenta `SELECT 1` com backoff limitado e falha
rápido se a URL for inválida.

### 7.5 Probes

- `identity-api`: readiness em `GET /health` na porta 8000 (retorna 503 quando o
  banco não responde) e liveness em `tcpSocket` na mesma porta. A liveness não
  depende do banco: uma indisponibilidade do Postgres deve tirar o pod do
  endpoints via readiness, não reiniciar todos os pods em loop.
- `agent-bridge`: readiness `tcpSocket` na 50051 permanece, pois o servidor não
  expõe HTTP. O initContainer `wait-for-db` cobre a disponibilidade inicial do
  banco.
- `postgres`: readiness `pg_isready`; adicionar liveness com o mesmo comando.

## 8. Workflows de publicação

### 8.1 Estrutura

Criar um workflow reutilizável e dois workflows finos por serviço:

```text
.github/workflows/
  publish-linx-core-image.yml        # workflow_call reutilizável
  publish-identity-api-image.yml     # paths do identity_api + shared
  publish-agent-bridge-image.yml     # paths do agent_bridge + shared
```

O workflow reutilizável recebe:

- `service` (`identity_api` ou `agent_bridge`);
- `dockerfile`;
- `repository` no Docker Hub;
- `context` (`linx_core`);
- `tag_prefix`.

Ele executa checkout, login no Docker Hub com
`DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`, build `linux/amd64` com labels
`org.opencontainers.image.revision` e `org.opencontainers.image.source`, push da
tag imutável `sha-<short-sha>` e da tag de canal correspondente ao branch
(`dev` em `develop`, `latest` em `main`), e valida o manifesto com
`docker manifest inspect`.

### 8.2 Gatilhos e filtros de caminho

Os dois workflows de serviço rodam apenas em:

- `push` para `develop` e `main`, com `paths` específicos;
- `workflow_dispatch` manual.

`identity-api`:

```yaml
paths:
  - "linx_core/services/identity_api/**"
  - "linx_core/shared/**"
  - "linx_core/alembic.ini"
  - ".github/workflows/publish-identity-api-image.yml"
  - ".github/workflows/publish-linx-core-image.yml"
```

`agent-bridge`:

```yaml
paths:
  - "linx_core/services/agent_bridge/**"
  - "linx_core/shared/**"
  - ".github/workflows/publish-agent-bridge-image.yml"
  - ".github/workflows/publish-linx-core-image.yml"
```

Consequências esperadas:

- Mudança só em `identity_api` publica apenas a imagem do identity-api.
- Mudança só em `agent_bridge` publica apenas a imagem do agent-bridge.
- Mudança em `linx_core/shared` publica as duas, porque as duas imagens incluem
  o shared.
- Mudança em frontend, docs, routing etc. não publica nenhuma das duas.
- `workflow_dispatch` ignora os filtros e publica sob demanda.
- `develop` publica `dev` e `sha-*`; `main` publica `latest` e `sha-*`. Um push
  em `main` não sobrescreve a tag `dev` usada pelo laboratório.

Observação: filtros `paths` não são avaliados em pushes de tag. Por isso os
workflows ficam restritos a branches (`develop`/`main`) e execução manual; tags
imutáveis são geradas pelo próprio workflow.

### 8.3 Secrets e permissões

Reutilizar os secrets já usados pelo workflow do tenant app:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN` (escopo de escrita nos dois repositórios)

O workflow usa `permissions: contents: read` e `concurrency` por serviço para
evitar duas publicações simultâneas da mesma imagem.

## 9. Mudanças por arquivo

| Arquivo | Mudança |
| --- | --- |
| `infra/kubernetes/base/identity-api.yaml` | Imagem Docker Hub, `imagePullPolicy: Always`, `envFrom`, initContainers `wait-for-db` e `migrate`. |
| `infra/kubernetes/base/agent-bridge.yaml` | Imagem Docker Hub, `imagePullPolicy: Always`, `envFrom`, initContainer `wait-for-db`. |
| `infra/kubernetes/base/postgres.yaml` | `strategy: Recreate`, liveness probe. |
| `infra/kubernetes/base/kustomization.yaml` | Mantém a lista de resources da base; as imagens Docker Hub ficam nos manifests e são sobrescritas pelos overlays. |
| `infra/kubernetes/overlays/dockerhub/kustomization.yaml` | Overlay explícito do laboratório. |
| `infra/kubernetes/overlays/ecr/kustomization.yaml` | Exemplo de troca de registry + `imagePullSecrets`. |
| `infra/kubernetes/linx-secrets.example.env` | Comentário e validação das chaves; host `postgres`. |
| `infra/kubernetes/README.md` | Runbook sem import local como padrão; Docker Hub, overlays, validação e rollback. |
| `linx_core/shared/src/linx_shared/db/wait.py` | Utilitário de espera/validação do banco. |
| `linx_core/shared/tests/test_db_wait.py` | Testes do utilitário. |
| `linx_core/services/identity_api/migrations/env.py` | Advisory lock antes das migrations. |
| `linx_core/shared/tests/test_migration_lock.py` | Testes unitários do advisory lock (o comportamento concorrente é validado no cluster). |
| `.github/workflows/publish-linx-core-image.yml` | Workflow reutilizável de build/push. |
| `.github/workflows/publish-identity-api-image.yml` | Caller com paths do identity-api. |
| `.github/workflows/publish-agent-bridge-image.yml` | Caller com paths do agent-bridge. |

## 10. Validação

### 10.1 Local (kind/k3s)

1. `kubectl apply -k infra/kubernetes --dry-run=client` sem erro.
2. Criar namespace e Secret com valores reais.
3. `kubectl apply -k infra/kubernetes`.
4. `kubectl -n linx get pods`: 2x identity-api, 2x agent-bridge e 1x postgres
   `Running`.
5. `kubectl -n linx describe pod -l app=identity-api`: evento de pull aponta para
   `docker.io/includeluisferreira/identity-api`; não há import local.
6. `kubectl -n linx logs deploy/identity-api -c migrate`: migration aplicada sem
   loop.
7. `kubectl -n linx logs deploy/identity-api -c wait-for-db`: mensagem de banco
   pronto.
8. `kubectl -n linx port-forward svc/identity-api 8000:8000` e
   `curl /health` retorna `{"status":"ok","db":true}`.
9. `grpcurl` no agent-bridge responde.
10. Recriar os dois pods do identity-api ao mesmo tempo e confirmar que o lock
    serializa as migrations.

### 10.2 Workflows

- Push que altera só `linx_core/services/identity_api/**`: somente o workflow do
  identity-api executa.
- Push que altera só `linx_core/services/agent_bridge/**`: somente o workflow do
  agent-bridge executa.
- Push que altera `linx_core/shared/**`: os dois executam.
- Push que altera `docs/**`: nenhum dos dois executa.
- Execução manual (`workflow_dispatch`) publica a imagem escolhida.

## 11. Rollback

- Voltar a tag no overlay/base para o `sha-<short-sha>` anterior e reaplicar com
  `kubectl apply -k`.
- `kubectl rollout undo deployment/identity-api -n linx` e
  `kubectl rollout undo deployment/agent-bridge -n linx`.
- Se necessário, usar o digest da imagem em vez da tag.
- O fallback de import local continua documentado no README, mas não é o caminho
  padrão.

## 12. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Docker Hub rate limit para pulls anônimos | Documentar `imagePullSecret` opcional e overlay ECR para produção. |
| Tag `dev` mutável causar drift | `imagePullPolicy: Always` no laboratório; tag `sha-*` ou digest em produção. |
| Secret ausente ou com placeholder | Serviços falham no startup; README valida as chaves antes do apply. |
| Migration concorrente | Advisory lock no `env.py` + initContainer único por pod. |
| Postgres com PVC RWO e rollout | `strategy: Recreate`. |
| URL de banco errada (`db` vs `postgres`) | Exemplo fixo em `linx-secrets.example.env` e README. |
| Workflow publicar imagem errada | Paths separados por serviço + `shared` nos dois + concurrency group. |
| Build em ARM gerar imagem incompatível com AWS | Workflow fixa `linux/amd64`; documentar build local com `--platform`. |

## 13. Tracking

Decisão do usuário: continuar na PR da issue #257 e registrar cada bloco de
implementação como comentário na PR, avisando o que foi feito. Não será criada
uma nova issue nem alterado o corpo da #257 nesta etapa.

Implicações:

- A branch de trabalho continua sendo `feat/257-k8s-service-discovery`.
- Cada entrega parcial (workflows, manifests, migration lock, runbook) deve
  gerar um comentário na PR descrevendo arquivos, validações e resultados.
- O escopo estrito do AGENTS.md continua valendo: só entram arquivos
  diretamente ligados a esta entrega.
- A PR só deve ser atualizada depois de validar os comandos localmente; o
  comentário deve refletir o resultado real, não o planejado.

## 14. O que fica para o plano de implementação

O plano detalhado deve quebrar o trabalho em tarefas verificáveis, com testes
antes da implementação quando houver código Python, validação de manifesto com
`kubectl apply -k --dry-run=client`, validação de workflow e ordem de commits.
Nenhum commit será feito sem autorização explícita do usuário.
