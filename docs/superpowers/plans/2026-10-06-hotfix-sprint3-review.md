# Hotfix — Revisão Sprint 3 (identity_api, routing, config/docs)

> Branch: `hot-fix`. Base: `develop` @ `ee9fa6d`.
> Origem: revisão geral dos PRs #183–#186. Escopo aprovado pelo usuário: P0 + P1 + P2.

## Contexto

A revisão da Sprint 3 encontrou um bug de perda de dados, riscos de segurança e
correção no serviço `routing`, além de inconsistências de config/compose/docs.
Este plano corrige apenas os itens de código testáveis agora. Itens de infra e
de feature maior ficam deferidos para suas issues (ver seção Deferidos).

## Global Constraints

- Python `>=3.12,<4.0`. Sem novas dependências além das já presentes salvo
  necessidade explícita de um task.
- Estilo: `black` line-length 79, `isort` profile `black`, `flake8`, `mypy`
  limpos. Testes: `pytest` com cobertura `--cov-fail-under=70` por pacote.
- Comandos por pacote: `poetry -C saas_backend/<pkg> run <task>`.
  Ex.: `poetry -C saas_backend/identity_api run pytest`.
- TDD obrigatório: teste vermelho primeiro, depois implementação, depois verde.
- Não adicionar comentários no código, exceto onde já é padrão do arquivo.
- Não quebrar contratos públicos existentes (rotas REST, assinatura de funções
  usadas por outros módulos).
- Toda mudança de schema exige migration Alembic em
  `saas_backend/migrations/versions/` com `down_revision` correto.
- Segurança: nunca logar segredos (AppKey, tokens, userinfo de URL).

## Deferidos (fora do escopo, com ruling)

- **`devices.py:91` — application_id do ChirpStack**: `Application` não tem
  coluna de id do ChirpStack e nada provisiona a application no broker.
  Correção exige provisionamento real (feature da Sprint 4, issues #58/#63).
  Ruling: não implementar aqui; documentar como pendência. Custo se errado:
  device ainda provisiona com UUID local errado até a Sprint 4.
- **Criptografia de AppKey em repouso** → issue #85.
- **TLS/mTLS gRPC e MQTT auth/TLS** → issues #81/#82.
- **DLQ com Redis Streams** → issue #105 (aqui só retry limitado).
- **Write path de `device_routes`** → issue #63.
- **Teste e2e de `build_ingest_payload`** → cobertura, não bug.

## Task 1: Corrigir provisionamento de devices e cliente ChirpStack (identity_api)

Arquivos principais: `saas_backend/identity_api/src/identity_api/routes/devices.py`,
`saas_backend/identity_api/src/identity_api/chirpstack_client.py`,
`saas_backend/identity_api/src/identity_api/config.py`,
`saas_backend/identity_api/src/identity_api/main.py` e os testes correspondentes.

Corrigir os achados abaixo, com teste vermelho→verde para cada um:

1. **[P0] Compensação apaga device pré-existente**
   `routes/devices.py:95-103`. Hoje `create_device` e `create_device_keys`
   estão no mesmo `try`, e o `except` chama `_delete_device_best_effort` mesmo
   quando `create_device` falhou (ex.: "already exists"). Isso apaga no
   ChirpStack um device que não criamos. Corrigir: rastrear se o device foi
   criado com sucesso (`created = False` antes; `created = True` após
   `create_device` retornar) e só compensar (deletar) quando `created` for
   verdadeiro. Falha em `create_device` → nenhuma deleção.
   Verificar contra o teste existente `tests/test_devices.py` e ajustar/adicionar
   caso que cubra "create_device falha → nenhum delete".

2. **[P1] TOCTOU apaga device do vencedor**
   `routes/devices.py:112-120`. No `IntegrityError` do `db.commit()` o código
   deleta no ChirpStack. Se duas requisições concorrentes criam o mesmo
   `dev_eui`, o perdedor remove o device que pode pertencer ao vencedor.
   Corrigir: no branch `IntegrityError`, apenas `db.rollback()` e retornar 409;
   **não** deletar no ChirpStack (a linha local já existe, implicando device
   já provisionado).

3. **[P1] Ordem delete local vs ChirpStack**
   `routes/devices.py:138-147`. Hoje deleta no ChirpStack e depois commita o
   delete local; se o commit falhar, o device sumiu externamente e a linha
   permanece. Corrigir: deletar a linha local e `db.commit()` primeiro; depois
   chamar `chirpstack.delete_device` de forma best-effort (logar falha, não
   falhar a request). Garantir que a operação é idempotente num retry (device
   local já ausente → 404).

4. **[P1] app_key só em `nwk_key`**
   `chirpstack_client.py:create_device_keys`. `DeviceKeys` hoje seta apenas
   `nwk_key`. Preencher também `app_key` com o mesmo valor informado, conforme
   o contrato armazenado. Cobrir com teste que verifica os dois campos.

5. **[P1] Canal gRPC inseguro**
   `chirpstack_client.py:12`. Adicionar settings de TLS em `config.py`
   (`chirpstack_use_tls: bool = False`, `chirpstack_ca_cert: str | None = None`).
   Em `ChirpStackClient.__init__`, usar `grpc.secure_channel` com as credenciais
   quando `use_tls` for verdadeiro; manter `grpc.insecure_channel` apenas quando
   falso (dev/local). Adicionar as chaves em `saas_backend/.env.example`.
   Nunca logar o token.

6. **[P1] Canal gRPC recriado por request**
   `routes/devices.py:20-27`. Reutilizar o canal/cliente em vez de criar e
   fechar a cada request. Criar um singleton lazy (ex.: `@lru_cache` sobre uma
   factory que lê `settings`) e registrar o fechamento no `lifespan` de
   `main.py` (`yield` + `client.close()` no shutdown). Manter a dependência
   `get_chirpstack_client` retornando o singleton (sem `finally: close()` por
   request).

7. **Testes**: ajustar `tests/test_devices.py` e
   `tests/test_chirpstack_client.py`; garantir que o comportamento 409/502 não
   regrediu e que a compensação só ocorre quando cabível. Rodar
   `poetry -C saas_backend/identity_api run pytest`.

## Task 2: Endurecer o serviço routing

Arquivos principais: `saas_backend/routing/src/routing/routing.py`,
`saas_backend/routing/src/routing/config.py`, `saas_backend/routing/tests/`, e
migration nova em `saas_backend/migrations/versions/`.

Corrigir os achados abaixo, com teste vermelho→verde onde aplicável:

1. **[P1] SSRF via `agent_endpoint`** `routing.py:95`. O endpoint vem do banco
   e só o scheme é validado; um endpoint malicioso faz o serviço postar em hosts
   internos/link-local (metadata cloud). Adicionar setting
   `agent_endpoint_allowlist` (lista de hosts, default vazia) em `config.py`.
   Implementar validação: parsear a URL, exigir scheme `http`/`https`, bloquear
   host `169.254.169.254`/link-local sempre, e, quando a allowlist não estiver
   vazia, exigir que o host esteja nela. Endpoint inválido → não envia, loga
   erro claro. Cobrir com testes de URL permitida, URL bloqueada e allowlist
   vazia.

2. **[P1] Fila descartada no shutdown** `routing.py:216`. Workers saem assim
   que `stop_event` é setado, descartando uplinks já enfileirados. Implementar
   drain: ao parar, os workers processam o que resta na fila antes de sair
   (ex.: `stop_event` marca parada de consumo do MQTT, mas a fila é esvaziada;
   usar sentinelas por worker após o `loop_stop`). Cobrir com teste que enfileira
   N itens, sinaliza stop e verifica que todos foram processados.

3. **[P1] Falha inicial de connect mata o processo** `routing.py:242`. Envolver
   o `connect()` inicial em retry com backoff (limite finito) em vez de deixar
   a exceção subir. Ajustar `deploy/docker-compose.yml` para o serviço `routing`
   depender do mosquitto healthy (healthcheck) em vez de `service_started`.

4. **[P1] `http_client.close()` antes dos workers** `routing.py:249`. O
   `join(timeout=5.0)` igual a `http_timeout_seconds` permite que um worker
   ainda esteja dentro de `client.post` quando o client é fechado. Fechar o
   client só após `join` confirmado (ou usar timeout de join maior que o HTTP e
   logar se algum worker não terminar).

5. **[P1] Fila sem cap de bytes** `routing.py:151`. A `Queue` limita por
   contagem (1000), não tamanho. Definir setting `max_payload_bytes`
   (default razoável, ex.: 65536) e descartar/logar uplinks acima do limite
   antes de enfileirar. Cobrir com teste.

6. **[P1] `lower(dev_eui)` sem índice e duplicados por caixa**
   `routing.py:75`. Adicionar migration criando índice único funcional
   `lower(dev_eui)` em `device_routes`. Manter a leitura com `func.lower`.
   Rodar `poetry -C saas_backend/identity_api run alembic -c ../alembic.ini
   upgrade head` (a migration pertence ao projeto do identity_api, que é o dono
   do Alembic). `down_revision` = revisão mais recente atual
   (`8bcf63c8173a`).

7. **[P1] Sem retry no POST ao client agent** `routing.py:111`. Adicionar retry
   limitado com backoff curto (ex.: 3 tentativas) para falhas transitórias
   (timeout/5xx). Esgotado o retry, logar erro e descartar o uplink. Não
   implementar DLQ (issue #105).

8. **[P2] Log vaza userinfo** `routing.py:127`. Redigir a userinfo embutida na
   URL antes de logar (ex.: mascarar `scheme://user:pass@host`).

9. **[P2] Tópico duplicado** `config.py:7`. Remover a duplicação entre o default
   de `mqtt_topic` no config e a constante de `routing.py`; uma fonte única.

10. **Testes**: ampliar `tests/test_routing.py` e `tests/test_config.py`. Rodar
    `poetry -C saas_backend/routing run pytest` e o lint do pacote.

## Task 3: Alinhar config, compose, código morto e docs

Arquivos: `deploy/.env.example`, `deploy/docker-compose.yml`,
`saas_backend/docker-compose.yml`, `saas_backend/.env.example`,
`tenant_app_template/docker-compose.yml`, `PROGRESS.md`, `README.md`,
`saas_backend/README.md`, `client_agent_api/README.md`, `.gitignore`.

1. **[P2] `CHIRPSTACK_DEVICE_PROFILE_ID` ausente no deploy** — adicionar em
   `deploy/.env.example` (e nas demais envs onde o identity_api roda). Sem isso
   `POST /api/v1/devices` retorna 500 no deploy.

2. **[P2] `saas_backend/docker-compose.yml` sem `routing`** — adicionar o
   serviço `routing` e as variáveis `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`,
   `MQTT_TOPIC`, `HTTP_TIMEOUT_SECONDS` no `saas_backend/.env.example`, mantendo
   coerência com `deploy/`.

3. **[P2] Código morto `mqtt_consumer.py`** — remover
   `client_agent_api/src/agent/mqtt_consumer.py` (não referenciado por
   `main.py`, superado pelo serviço `routing`) e as referências nos READMEs que
   ainda o descrevem como ativo.

4. **[P2] Porta errada no compose do tenant** —
   `tenant_app_template/docker-compose.yml` mapeia `${TENANT_PORT}:8000` mas o
   container ouve 8002; corrigir para `:8002` (coerente com `deploy/`).

5. **[P2] Drift do `PROGRESS.md`** — marcar `#46` e `#48` como concluídas
   (mergeadas em `e947a64` e `ba0040f`) e atualizar o total de issues
   concluídas.

6. **[P2] READMEs stale** — corrigir `README.md` (JWT/WebSocket prometidos em
   serviços onde não existem; templates citados ausentes), `saas_backend/README.md`
   (rota `GET /` inexistente; caminho de listagem de tenant) e referências ao
   `mqtt_consumer`.

7. **[P2] `.env` reais vs gitignore** — verificar `.gitignore` cobre
   `saas_backend/.env`, `deploy/.env`, `client_agent_api/.env`,
   `tenant_app_template/.env`. Se algum estiver rastreado, remover do índice
   com `git rm --cached` e garantir a regra no `.gitignore`. Não logar nem
   imprimir conteúdo de segredos.

Este task não altera lógica de aplicação; não exige TDD. Verificar com
`git status` e inspeção dos arquivos alterados.

## Verificação final

- Rodar a suíte completa por pacote afetado e os lints.
- Revisão final da branch inteira antes de abrir o PR `hot-fix` → `develop`.
