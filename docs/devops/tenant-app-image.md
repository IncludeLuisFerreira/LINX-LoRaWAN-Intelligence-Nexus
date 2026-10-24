# Publicação da imagem do Tenant App

A imagem do `tenant_app` é o ambiente Docker mínimo provisionado para cada
Aplicação (RF-010). O provisionador do Linx Core precisa de uma referência
pública ou acessível no registro para executar `docker run` em cada tenant.

Esta página documenta o script de build e publicação da issue #64.

## Imagem publicada

A publicação de referência do MVP está no Docker Hub, com visibilidade
pública (o provisionador não precisa de `docker login` para o pull):

| Item | Valor |
| --- | --- |
| Referência | `includeluisferreira/linx-tenant-app:latest` |
| Digest | `sha256:ba1837d5962f41542c26411db1c9f4c4202540ac50091603f42037d706855f75` |
| Plataforma | `linux/amd64` |
| Publicada em | 2026-10-24 |

O digest acima identifica a publicação feita durante a implementação da #64.
Como `latest` é mutável, use o digest para fixar exatamente essa versão:

```bash
PROVISION_IMAGE=includeluisferreira/linx-tenant-app@sha256:ba1837d5962f41542c26411db1c9f4c4202540ac50091603f42037d706855f75
```

## Dependência

O contexto de build é `client/tenant_app/`, criado pela issue #58. Enquanto a
#58 não estiver integrada em `develop`, aponte o script para o worktree que
contém o diretório:

```bash
./scripts/publish_tenant_app_image.sh \
  --context /caminho/para/LINX/client/tenant_app \
  --build-only
```

## Pré-requisitos

- Docker 20+ com BuildKit.
- `poetry.lock` presente no contexto (build reproduzível das dependências).
- Docker Hub: `docker login` com um token que tenha permissão de push.
- ECR: AWS CLI configurada e permissão para `ecr:CreateRepository`,
  `ecr:DescribeRepositories`, `ecr:GetAuthorizationToken` e push.

## Docker Hub (MVP)

```bash
docker login
./scripts/publish_tenant_app_image.sh \
  --registry dockerhub \
  --repository includeluisferreira/linx-tenant-app \
  --tag latest
```

Sem `--repository`, o padrão é
`includeluisferreira/linx-tenant-app`. O script:

1. executa `docker build --pull --platform linux/amd64`;
2. roda um smoke test importando `tenant_app.app`;
3. faz login/push usando a sessão existente do Docker;
4. valida o manifesto publicado com `docker manifest inspect`.

## Amazon ECR

```bash
AWS_REGION=us-east-1 \
ECR_REPOSITORY=linx-tenant-app \
./scripts/publish_tenant_app_image.sh \
  --registry ecr \
  --tag latest
```

O script obtém a conta via `aws sts get-caller-identity`, cria o repositório
na primeira execução, autentica no ECR e publica a tag.

## Apenas build

Use `--build-only` para validar localmente sem login, push ou credenciais:

```bash
./scripts/publish_tenant_app_image.sh --build-only
```

## Uso no provisionamento

Após a publicação, configure o provisionador com a referência retornada pelo
script:

```bash
PROVISION_IMAGE=includeluisferreira/linx-tenant-app:latest
```

Adicione a linha acima ao `linx_core/.env` (ou exporte no ambiente). Em
`linx_core/docker-compose.yml`, a variável é repassada ao
`docker_provisioner`:

```yaml
environment:
  PROVISION_IMAGE: ${PROVISION_IMAGE:-linx-tenant-app:latest}
```

Para ECR, use a referência completa:

```bash
PROVISION_IMAGE=<conta>.dkr.ecr.<região>.amazonaws.com/linx-tenant-app:latest
```

Se o registro for privado, o host do `docker_provisioner` precisa estar
autenticado (`docker login`) ou usar as credenciais do ECR antes de provisionar.

## Verificação

```bash
docker pull includeluisferreira/linx-tenant-app:latest
docker run --rm includeluisferreira/linx-tenant-app:latest \
  python -c "import tenant_app.app"
```

O pull também pode ser conferido com:

```bash
docker manifest inspect includeluisferreira/linx-tenant-app:latest
docker image inspect includeluisferreira/linx-tenant-app:latest \
  --format '{{.Os}}/{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
```

Teste rápido do runtime:

```bash
docker run -d --rm --name tenant-app-check -p 18080:8000 \
  -e APP_ID=check-app \
  -e MQTT_TOPIC='application/check-app/device/+/event/up' \
  -e DB_PASSWORD=check-db-password \
  -e SERVICE_TOKEN=check-service-token-0123456789abcdef \
  includeluisferreira/linx-tenant-app:latest

curl -fsS http://localhost:18080/health
# {"status":"ok","app_id":"check-app"}

curl -fsS -H 'X-Service-Token: check-service-token-0123456789abcdef' \
  http://localhost:18080/info
# {"app_id":"check-app","mqtt_topic":"...","db_password_configured":true}

docker rm -f tenant-app-check
```

## Republicação

O script reconstrói a imagem a partir de `client/tenant_app/`. Depois que a
issue #58 for integrada em `develop`, execute novamente para publicar o
conteúdo definitivo do template:

```bash
./scripts/publish_tenant_app_image.sh \
  --registry dockerhub \
  --repository includeluisferreira/linx-tenant-app \
  --tag latest
```

Para manter uma versão imutável, publique também uma tag de release:

```bash
./scripts/publish_tenant_app_image.sh \
  --registry dockerhub \
  --repository includeluisferreira/linx-tenant-app \
  --tag tenant-app-v0.1.0
```

## Problemas comuns

| Erro | Causa provável | Ação |
| --- | --- | --- |
| `contexto inválido ... Dockerfile não encontrado` | `client/tenant_app/` ainda não existe no branch. | Faça merge/checkout da #58 ou use `--context /caminho/tenant_app`. |
| `Docker Hub não autenticado` | Sessão Docker expirada ou token sem permissão de push. | Execute `docker login` e confirme o usuário. |
| `unauthorized` no `docker push` | Token sem `write` ou repositório de outro namespace. | Gere um token com escrita ou ajuste `--repository`. |
| `manifest unknown` após o push | Push ainda em propagação ou tag errada. | Repita `docker manifest inspect` com a mesma tag. |
| `exec format error` | Imagem `linux/amd64` executada em host incompatível sem emulação. | Use host amd64 ou publique também a plataforma necessária. |

## Publicação via GitHub Actions

O workflow manual `.github/workflows/publish-tenant-app-image.yml` executa o
mesmo script no Docker Hub. Configure os secrets do repositório:

| Secret | Uso |
| --- | --- |
| `DOCKERHUB_USERNAME` | Usuário do Docker Hub. |
| `DOCKERHUB_TOKEN` | Token com permissão de leitura e escrita. |

Depois, dispare o workflow em **Actions → Publish Tenant App Image → Run
workflow**, informando `tag` e `repository`.

## Segurança

- Nunca versione tokens ou credenciais de registro.
- Prefira tokens de escopo mínimo no Docker Hub.
- No ECR, prefira credenciais temporárias ou OIDC em vez de chaves estáticas.
- A tag `latest` é mutável; para releases, publique também uma tag imutável
  (por exemplo, `tenant-app-v1.0.0`).
