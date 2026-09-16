# Design: tenant_app_template consumindo o middleware compartilhado

**Data:** 2026-09-16
**Escopo:** topologia/configuração/documentação (sem código Python)
**Relacionado:** issue #34 / PR #160 (Model A — `client_agent_api` como middleware compartilhado)

## Contexto

No Modelo A, o `client_agent_api` é o **middleware compartilhado** entre o
`tenant_app_template` e o `saas_backend` (confirmado no PRD — UC01/UC02/UC06/UC09 —
em `README.md` e `docs/estrutura_de_pastas/estrutura.md`). O tenant app **não**
deve instanciar um Client Agent por aplicação; ele deve **se comunicar** com o
middleware compartilhado.

O `tenant_app_template/docker-compose.yml` ainda tinha um serviço `client_agent`
que buildava `../client_agent_api` (desenho antigo, Modelo B). Esse serviço foi
removido no working tree, mas restaram inconsistências:

- o compose não sobe o tenant app em lugar nenhum (só `timescaledb`);
- `.env.example`, `README.md` e a porta do tenant ainda refletem o desenho antigo;
- não existe configuração do endereço do middleware compartilhado.

## Objetivo

Representar corretamente o ambiente tenant no template: subir `tenant_app` +
`timescaledb`, com o tenant app configurado para falar com o **middleware
compartilhado** via `CLIENT_AGENT_URL`. A implementação do cliente HTTP
tenant→middleware fica para issue futura.

## Não-objetivos

- Implementar o cliente HTTP do tenant app para o middleware.
- Implementar proxy REST/WebSocket, gRPC server do middleware, JWT/RBAC.
- Alterar o `client_agent_api` ou o `saas_backend`.
- Provisionamento/orquestração real do contêiner pelo SaaS.

## Design

### `tenant_app_template/docker-compose.yml`

- Mantém `timescaledb` como está.
- Remove o serviço `client_agent` (já removido no working tree).
- Adiciona `tenant_app`:

```yaml
  tenant_app:
    build: .
    restart: unless-stopped
    environment:
      - CLIENT_AGENT_URL=${CLIENT_AGENT_URL}
      - APP_ID=${APP_ID}
      - MQTT_TOPIC=${MQTT_TOPIC}
      - DB_HOST=timescaledb
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_NAME=${DB_NAME}
    depends_on:
      timescaledb:
        condition: service_healthy
    ports:
      - "${TENANT_PORT}:8000"
```

- O `Dockerfile` do tenant já roda `tenant.main:app` na porta `8000`; sem mudança.
- O middleware é **externo** ao compose (compartilhado), então não há
  `depends_on` nem serviço de middleware aqui.

### `tenant_app_template/.env.example`

| Variável            | Valor                     | Descrição                                      |
| ------------------- | ------------------------- | ---------------------------------------------- |
| `CLIENT_AGENT_URL`  | `http://localhost:8001`   | URL base do middleware compartilhado.          |
| `APP_ID`            | `app-abc123`              | Identidade da aplicação.                       |
| `MQTT_TOPIC`        | `au915_0/gateway/+/event/up` | Tópico MQTT de uplink.                     |
| `TENANT_PORT`       | `8002`                    | Porta exposta do tenant app (evita colisão com o middleware 8001). |
| `DB_USER`           | `tenant`                  | Usuário do PostgreSQL/TimescaleDB.             |
| `DB_PASSWORD`       | `changeme`                | Senha do banco.                                |
| `DB_NAME`           | `tenantdb`                | Nome do banco.                                 |

> `CLIENT_AGENT_URL` é resolvido/injetado no provisionamento. Em dev na mesma
> máquina, `http://localhost:8001` funciona; dentro do container é preciso um
> endereço alcançável (IP do host ou rede Docker compartilhada).

### `tenant_app_template/README.md`

- Reescreve a seção "Docker Compose (ambiente tenant completo)": sobe
  `timescaledb` + `tenant_app`; o tenant app consome o middleware compartilhado.
- Remove referências ao `client_agent` por-tenant.
- Atualiza a tabela de variáveis com `CLIENT_AGENT_URL` e `TENANT_PORT=8002`.
- Nota: o cliente HTTP tenant→middleware é issue futura; aqui entra apenas a
  configuração/topologia.

## Validação

- `cd tenant_app_template && cp .env.example .env && docker compose config`
  resolve sem erro e mostra os serviços `timescaledb` e `tenant_app`, com
  `ports` `"8002:8000"` e `CLIENT_AGENT_URL` no `tenant_app`.
- Nenhuma alteração de código Python/testes; `pytest` do tenant permanece verde.

## Riscos e mitigações

- **Colisão de porta em dev co-localizado:**   default `TENANT_PORT=8002` evita o
  8001 do middleware.
- **`CLIENT_AGENT_URL` inalcançável de dentro do container:** documentado no
  `.env.example` e no README (usar IP do host ou rede compartilhada).
