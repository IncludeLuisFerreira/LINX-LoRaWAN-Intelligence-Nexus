# Backlog de Sprints — LINX (Produto Real)

**Time:** 3 devs  
**Início:** 27/08/2026  
**MVP entregável:** SaaS Multi-Tenant funcional com fluxo IoT ponta-a-ponta  
**Princípio:** cada sprint termina com software deployável e testável. Nada é "para depois".

---

## Visão do MVP

O MVP é considerado completo quando:
1. Um cliente consegue se cadastrar, criar uma Aplicação e ter seu ambiente isolado provisionado automaticamente na nuvem.
2. Um sensor LoRaWAN envia dados que aparecem no dashboard do cliente em tempo real (≤ 2s).
3. O cliente consegue criar uma regra que dispara um downlink ou alerta quando a condição é violada.
4. Dois clientes distintos não conseguem ver dados um do outro (isolamento comprovado).
5. O sistema se recupera de falhas sem intervenção manual.

---

## Mapa de Sprints

| Sprint | Período | Duração | Entrega ao final |
|:---|:---|:---|:---|
| S1 | 27/08 → 09/09 | 14 dias | Fundação: contratos, CI/CD, infra local rodando |
| S2 | 10/09 → 23/09 | 14 dias | SaaS Backend + Client Agent na AWS, gRPC funcionando |
| S3 | 24/09 → 07/10 | 14 dias | ChirpStack integrado, uplink ponta-a-ponta, WebSocket |
| S4 | 08/10 → 21/10 | 14 dias | Multi-tenant real: provisionamento automático de Docker por app |
| S5 | 22/10 → 04/11 | 14 dias | Autenticação JWT/OAuth2, RBAC, TLS em todas as camadas |
| S6 | 05/11 → 18/11 | 14 dias | Motor de regras, downlink, alertas (Telegram/Email) |
| S7 | 19/11 → 02/12 | 14 dias | Resiliência: retry, circuit breaker, DLQ, graceful shutdown |
| S8 | 03/12 → 14/12 | 12 dias | Observabilidade, hardening, QR Code, demo final |

---

## Sprint 1 — Fundação e Contratos (27/08 → 09/09)

**Meta:** Repositórios estruturados, CI verde, contratos de API definidos, infra local subindo com um comando.

### Aluno 1 — Frontend
- [ ] Scaffold `frontend/` com React + Vite + TypeScript + TailwindCSS.
- [ ] Configurar ESLint + Prettier + husky (pre-commit).
- [ ] Criar estrutura de rotas: `/login`, `/orgs`, `/apps/:id`, `/devices`, `/dashboard/:appId`.
- [ ] Implementar Layout shell (Sidebar + AppBar + ContentArea) responsivo.
- [ ] Tela de Login (UI + mock de autenticação local).
- [ ] Configurar Axios instance com `baseURL` e interceptors prontos para JWT.
- [ ] Criar `openapi-stub.yaml` com os contratos REST que o frontend espera (acordar com Aluno 2).

### Aluno 2 — SaaS Backend
- [ ] Scaffold `saas_backend/` com FastAPI + Poetry.
- [ ] `infra/docker-compose.base.yml`: PostgreSQL 15, Redis 7, Mosquitto MQTT.
- [ ] Models SQLAlchemy 2.0: `organizations`, `applications`, `users`, `roles` (todos com `id UUID PK`).
- [ ] Alembic migration inicial criando as 4 tabelas.
- [ ] CRUD REST de Organizações: `POST/GET/PATCH/DELETE /api/v1/orgs`.
- [ ] CRUD REST de Aplicações vinculadas a org (`org_id FK`).
- [ ] GitHub Actions: `black`, `flake8`, `mypy`, `pytest` (cobertura ≥ 70%).
- [ ] Entregar stub OpenAPI até **03/09** para o Aluno 1 desenvolver contra mock.

### Aluno 3 — Client Agent + Tenant Template
- [ ] Scaffold `client_agent_api/` e `tenant_app_template/` com FastAPI.
- [ ] Schema TimescaleDB em `tenant_app_template/db/schema.sql`: hypertable `telemetry` (`time TIMESTAMPTZ`, `dev_eui TEXT`, `payload JSONB`, `rssi INT`, `snr FLOAT`).
- [ ] Consumidor MQTT básico (`paho-mqtt`): subscribe em `application/+/device/+/event/up`, logar payload.
- [ ] Definir `proto/saas_agent.proto`: `service AgentBridge { rpc GetAppConfig(AppId) returns (AppConfig); rpc IngestTelemetry(TelemetryEvent) returns (Ack); }`.
- [ ] Gerar stubs gRPC Python.
- [ ] Dockerfile multi-stage para `client_agent_api`.
- [ ] `docker-compose.yml` do tenant: `client_agent_api` + `timescaledb`.

**Critérios de Aceitação S1:**
- `docker-compose -f infra/docker-compose.base.yml up` sobe sem erros.
- `pytest saas_backend/` passa com ≥ 70% coverage.
- `npm run build` no frontend compila sem erros.
- `docker build` do client_agent_api conclui com sucesso.
- CI verde nos 3 módulos.

---

## Sprint 2 — Dois Serviços na AWS com gRPC (10/09 → 23/09)

**Meta:** SaaS Backend e Client Agent deployados na AWS, comunicando via gRPC. Prova de comunicação documentada.

### Aluno 1 — Frontend
- [ ] Tela de Cadastro de Organização consumindo `POST /api/v1/orgs` (backend AWS).
- [ ] Tela de Cadastro de Aplicação com select de Organization.
- [ ] Dockerfile do frontend (nginx alpine servindo build estático).
- [ ] Script `deploy-frontend.sh`: build → push → deploy em EC2 ou S3+CloudFront.
- [ ] Nginx local roteando `/api/*` → SaaS Backend AWS.

### Aluno 2 — SaaS Backend
- [ ] gRPC Server em `saas_backend/grpc_server.py`: método `GetAppConfig` retornando `db_host`, `db_port`, `mqtt_topic` da aplicação.
- [ ] Endpoint `GET /health` retornando status do DB e do gRPC server.
- [ ] Deploy em EC2 `t3.small` com Docker Compose (app + PostgreSQL local para MVP).
- [ ] Security Group AWS: inbound 8000 (REST), 50051 (gRPC), 22 (SSH).
- [ ] Nginx com TLS (Let's Encrypt ou certificado autoassinado para dev).
- [ ] Tabela `device_routes` (`dev_eui`, `app_id`, `agent_endpoint`) para roteamento futuro.

### Aluno 3 — Client Agent
- [ ] gRPC Client em `client_agent_api/grpc_client.py`: conecta ao SaaS Backend porta 50051, chama `GetAppConfig` no startup.
- [ ] Endpoint `POST /ingest`: recebe payload JSON, valida schema, persiste no TimescaleDB.
- [ ] Pipeline: Mosquitto → `mqtt_consumer.py` → parse → `POST /ingest` → TimescaleDB.
- [ ] Deploy em segunda instância EC2 (ou porta 8001 na mesma EC2).
- [ ] Log do `AppConfig` recebido via gRPC (prova de comunicação).
- [ ] README com `curl` documentando: (1) criar org via SaaS REST, (2) ingestar telemetria via Client Agent.

**Critérios de Aceitação S2:**
- Dois serviços distintos rodando na AWS com URLs/portas acessíveis.
- Log do Client Agent mostrando `AppConfig` recebido do SaaS via gRPC.
- `curl POST /api/v1/orgs` cria organização no banco AWS.
- `curl POST /ingest` persiste telemetria no TimescaleDB.
- Frontend acessível via navegador cadastrando Org/App no backend AWS.

---

## Sprint 3 — ChirpStack, Uplink Ponta-a-Ponta e WebSocket (24/09 → 07/10)

**Meta:** Fluxo completo Sensor → ChirpStack → MQTT → Client Agent → TimescaleDB → WebSocket → Frontend funcionando.

### Aluno 1 — Frontend
- [ ] Integrar `html5-qrcode` para leitura de QR Code TR005 (parsear `SchemaID`, `JoinEUI`, `DevEUI`, `AppKey`).
- [ ] Wizard de Onboarding (3 steps): Scan QR → Confirmar dados → Selecionar App → Submeter.
- [ ] Tela de Dashboard com gráfico de linha (Recharts ou Chart.js) consumindo histórico REST.
- [ ] Conectar Dashboard ao WebSocket do Client Agent: atualizar gráfico em tempo real.
- [ ] Fallback: se WebSocket cair, polling REST `GET /telemetry` a cada 5s.

### Aluno 2 — SaaS Backend
- [ ] Cliente ChirpStack gRPC em `saas_backend/chirpstack_client.py` usando `chirpstack-api` Python.
- [ ] Endpoint `POST /api/v1/devices`: valida payload → salva em `devices` (`id UUID`, `dev_eui UNIQUE`, `app_id FK`, `join_eui`, `app_key` criptografado) → provisiona no ChirpStack via gRPC.
- [ ] Serviço de roteamento: ao receber uplink MQTT, consulta `device_routes` e encaminha para o endpoint correto do Client Agent.
- [ ] ChirpStack Application configurado para publicar em `application/{app_id}/device/{dev_eui}/event/up`.

### Aluno 3 — Client Agent
- [ ] Refinar `mqtt_consumer.py` para parsear payload ChirpStack v4: extrair `devEUI`, `fCnt`, `rxInfo`, `object`.
- [ ] Normalização: transformar `object` (ex: `{"temperature": 25.5}`) em registro TimescaleDB.
- [ ] Endpoint `GET /api/v1/telemetry/{dev_eui}?from=&to=&limit=` com paginação cursor-based.
- [ ] WebSocket server FastAPI (`@app.websocket("/ws/telemetry/{app_id}")`): broadcast para clients conectados quando chega nova mensagem MQTT.
- [ ] `docker-compose.yml` do `infra/` com ChirpStack v4 completo (já existe em `infra/`).

**Critérios de Aceitação S3:**
- Publicação via `mosquitto_pub` no tópico correto → dado aparece no TimescaleDB.
- WebSocket conectado no frontend recebe dado em ≤ 2s após publicação MQTT.
- Wizard de QR Code cria device no PostgreSQL global e no ChirpStack (verificável na UI).
- `GET /telemetry` retorna dados paginados em JSON.
- Dois tenants distintos: telemetria do tenant A não aparece no WebSocket do tenant B.

---

## Sprint 4 — Multi-Tenant Real: Provisionamento Automático (08/10 → 21/10)

**Meta:** Criação de Aplicação dispara provisionamento automático de container Docker isolado na nuvem. Isolamento comprovado.

### Aluno 1 — Frontend
- [ ] Exibir status de provisionamento da Aplicação: `PENDING → PROVISIONING → RUNNING → ERROR` com indicador visual.
- [ ] Polling `GET /api/v1/applications/{app_id}/status` a cada 3s até status `RUNNING`.
- [ ] Tela de Dispositivos da Aplicação: listar devices, status online/offline, última telemetria.
- [ ] Exibir UUID de cada recurso na UI com botão "copiar".

### Aluno 2 — SaaS Backend
- [ ] Endpoint `POST /api/v1/applications/{app_id}/provision`: usar `docker-py` para `docker run` a partir da imagem `tenant_app_template`, porta dinâmica (range 8100-9100), variáveis de ambiente injetadas (`APP_ID`, `DB_PASSWORD`, `MQTT_TOPIC`).
- [ ] Tabela `application_instances` (`app_id FK`, `container_id`, `host`, `port`, `status`, `provisioned_at`).
- [ ] Trigger automático: ao criar Aplicação via `POST /api/v1/applications`, chamar provision em background (FastAPI `BackgroundTasks`).
- [ ] Endpoint `GET /api/v1/applications/{app_id}/status` retornando status do container (`docker inspect`).
- [ ] Garantir que **100% dos recursos** usam UUID v4: constraint `UNIQUE` + validação em middleware.
- [ ] Atualizar `device_routes` com endpoint real do container provisionado.

### Aluno 3 — Client Agent + Tenant Template
- [ ] Imagem Docker do `tenant_app_template` publicada no ECR (ou Docker Hub para MVP).
- [ ] Client Agent recebe `APP_ID` e `MQTT_TOPIC` via variável de ambiente no startup.
- [ ] Isolamento de rede: cada container tenant em Docker network isolada (`bridge` dedicada por app).
- [ ] Endpoint `/health` no tenant retornando status do TimescaleDB e do consumidor MQTT.
- [ ] Teste de isolamento: script Python que cria 2 apps, publica telemetria em cada uma e verifica que os dados não se cruzam.

**Critérios de Aceitação S4:**
- Criar Aplicação via API → container Docker sobe automaticamente em ≤ 60s.
- `docker ps` mostra containers distintos para cada app com portas diferentes.
- Telemetria do tenant A não é visível no endpoint do tenant B (teste automatizado).
- `GET /applications/{app_id}/status` retorna `RUNNING` após provisionamento.
- Todos os IDs são UUID v4 (query SQL comprovando).

---

## Sprint 5 — Autenticação, RBAC e TLS (22/10 → 04/11)

**Meta:** Sistema seguro de ponta a ponta. Nenhum endpoint acessível sem autenticação. TLS em todas as camadas.

### Aluno 1 — Frontend
- [ ] Login JWT completo: `POST /auth/login` → armazenar `access_token` em memória + `refresh_token` em httpOnly cookie.
- [ ] AuthGuard de rotas: redirecionar para `/login` se token expirado (decodificar `exp` do JWT).
- [ ] Componente `<Can permission="device:create">` que só renderiza se usuário tiver permissão.
- [ ] Tela "Gestão de Usuários": listar, convidar (gerar link), alterar papel, desativar.
- [ ] HTTPS no deploy do frontend (CloudFront ou Nginx + certificado).

### Aluno 2 — SaaS Backend
- [ ] OAuth2 Password Flow: endpoint `POST /auth/login` retornando JWT (access: 15min, refresh: 7d).
- [ ] Senhas com bcrypt (`passlib[bcrypt]`, rounds=12).
- [ ] Endpoint `POST /auth/refresh`: valida refresh token, emite novo access token.
- [ ] RBAC: tabelas `permissions` (resource, action) e `user_roles`. Middleware `Depends(require_permission(...))` em 100% dos endpoints.
- [ ] TLS 1.3 em todos os endpoints (Let's Encrypt na AWS).
- [ ] Rate limiting com `slowapi` (Redis backend): 100 req/min por IP, 10 req/min para `/auth/login`.
- [ ] Convidar usuário: `POST /api/v1/orgs/{org_id}/invite` gera token de convite (TTL 48h no Redis).

### Aluno 3 — Client Agent
- [ ] TLS no Mosquitto: porta 8883 para MQTT over TLS. Rejeitar conexões não-TLS na porta 1883.
- [ ] mTLS entre Client Agent e SaaS Backend: gRPC com `ssl_channel_credentials` (`ca.crt`, `client.crt`, `client.key`).
- [ ] Validação de JWT no Client Agent: middleware FastAPI verifica `Authorization: Bearer <token>` contra chave pública do SaaS Backend.
- [ ] Endpoint `/health` protegido por `X-Service-Token` (token de serviço, não JWT de usuário).
- [ ] Criptografar `app_key` em repouso no TimescaleDB com AES-256-GCM.

**Critérios de Aceitação S5:**
- Login end-to-end: frontend → JWT → acesso ao dashboard.
- `curl` sem token retorna `401`; token com papel errado retorna `403`.
- TLS 1.3 confirmado nos logs do Nginx e do gRPC.
- MQTT na porta 1883 rejeita conexão (testar com `mosquitto_sub -p 1883` falhando).
- gRPC entre SaaS e Client Agent usa mTLS (logs de handshake com certificado cliente).
- Rate limiting: 11ª tentativa de login em 1 min retorna `429`.

---

## Sprint 6 — Motor de Regras, Downlink e Alertas (05/11 → 18/11)

**Meta:** Cliente consegue criar regras que disparam ações reais: downlink para o sensor e notificação por Telegram/Email.

### Aluno 1 — Frontend
- [ ] Tela "Regras de Negócio": formulário com `sensor_field`, `operator` (`>`, `<`, `==`, `!=`), `threshold`, `action_type` (`downlink`, `telegram`, `email`).
- [ ] Tela "Alertas": tabela com alertas disparados (`alert_id`, `rule_id`, `dev_eui`, `triggered_at`, `message`), ordenados desc.
- [ ] Botão "Enviar Comando" (Downlink manual) na tela de dispositivo: modal com campo payload JSON.
- [ ] Tela "Histórico" com filtros: date range picker, select de dispositivo, tipo de métrica.

### Aluno 2 — SaaS Backend
- [ ] Endpoint `POST /api/v1/rules`: persiste regra no PostgreSQL global e replica para o Docker Cliente via gRPC (`SyncRule`).
- [ ] Endpoint `POST /api/v1/downlinks`: valida permissão → aciona ChirpStack via gRPC (`DeviceQueueService.Enqueue`).
- [ ] Serviço de notificação em `saas_backend/notifications.py`: integração com Telegram Bot API e SMTP (email). Configurável por aplicação.
- [ ] Tabela `alerts` (`id UUID`, `rule_id FK`, `dev_eui`, `triggered_at`, `message`, `notified`).

### Aluno 3 — Client Agent + Motor de Regras
- [ ] Motor de Regras em `tenant_app_template/rules_engine.py`: avalia regras a cada telemetria inserida usando `asteval` (sem `eval` nativo).
- [ ] Ao violar regra: publicar evento `rule_violated` para o SaaS Backend via gRPC (`ReportViolation`).
- [ ] Tabela `downlink_queue` (`id UUID`, `dev_eui`, `payload JSONB`, `scheduled_at`, `sent_at`, `status ENUM(pending, sent, failed)`).
- [ ] Worker async: processa `downlink_queue` a cada 30s, chama SaaS Backend para enfileirar no ChirpStack.
- [ ] Endpoint `POST /rules/sync` (gRPC): recebe regra do SaaS Backend e persiste localmente no tenant.

**Critérios de Aceitação S6:**
- Criar regra "temperatura > 40" → publicar telemetria com temp=45 → alerta aparece na tela em ≤ 5s.
- Downlink manual via frontend → log do ChirpStack mostrando mensagem enfileirada.
- Notificação Telegram recebida após violação de regra (configurar bot de teste).
- Motor de regras de tenant A não acessa dados do tenant B.
- `downlink_queue` registra status `sent` após confirmação do ChirpStack.

---

## Sprint 7 — Resiliência: Retry, Circuit Breaker e DLQ (19/11 → 02/12)

**Meta:** Sistema se recupera de falhas sem intervenção manual. Nenhuma mensagem perdida silenciosamente.

### Aluno 1 — Frontend
- [ ] Interceptador Axios: retry automático em 5xx (3 tentativas, backoff 1s/2s/4s).
- [ ] Reconexão WebSocket com backoff exponencial (1s, 2s, 4s, 8s, max 30s).
- [ ] Indicador "Modo Offline" no header quando backend retorna 5xx ou timeout.
- [ ] Tela "Status do Sistema": consumir `GET /health` de todos os serviços, exibir verde/vermelho.

### Aluno 2 — SaaS Backend
- [ ] Retry com backoff exponencial para chamadas gRPC ao ChirpStack: `tenacity` com `wait_exponential(min=4, max=60)`, max 5 tentativas (RF-042).
- [ ] Circuit Breaker (`pybreaker`) para chamadas ao Client Agent: abre após 5 falhas, meio-aberto após 30s, fallback retorna `503`.
- [ ] Dead Letter Queue com Redis Streams (`failed_events`): mensagens MQTT que falharam após 3 retries.
- [ ] Retry para provisionamento Docker: 3 tentativas com backoff antes de marcar app como `ERROR`.
- [ ] Backup automático do PostgreSQL: `pg_dump` diário para S3 via cron no container.

### Aluno 3 — Client Agent
- [ ] Retry com backoff para publicações MQTT (downlinks): se `publish()` falhar, enfileirar em `downlink_queue`.
- [ ] `HEALTHCHECK` no Dockerfile: `curl -f http://localhost:8000/health || exit 1`.
- [ ] Graceful shutdown: handler `SIGTERM` fecha conexão MQTT, flush de queries pendentes, encerra.
- [ ] Se container tenant não responder ao health check por 60s: publicar evento `container_down` para o SaaS Backend.
- [ ] Reconexão automática do consumidor MQTT: se conexão cair, tentar reconectar com backoff.

**Critérios de Aceitação S7:**
- Circuit breaker abre após 5 falhas (matar Client Agent, fazer 5 requests, verificar estado `OPEN` nos logs).
- DLQ contém mensagens após 3 retries falhos (`redis-cli XREAD` ou logs).
- WebSocket reconecta automaticamente após `docker stop` + `docker start` do Client Agent.
- Graceful shutdown: logs mostrando `Closing MQTT...`, `Flushing DB pool...`, `Shutdown complete.`
- Backup do PostgreSQL restaurável (dropar tabela, restaurar dump, verificar dados).

---

## Sprint 8 — Observabilidade, Hardening e Demo Final (03/12 → 14/12)

**Meta:** Sistema observável, seguro e demonstrável. MVP completo e documentado.

### Aluno 1 — Frontend
- [ ] Tela "Logs de Auditoria": `timestamp`, `user`, `action`, `resource`, `ip_address`.
- [ ] Dashboard de métricas: latência média, devices ativos, alertas/hora.
- [ ] Polir UI: loading skeletons, empty states, responsividade mobile.
- [ ] Gravar vídeo de demonstração (5-10 min): QR Code scan → telemetria em tempo real → alerta → downlink.
- [ ] `docs/DEMO_SCRIPT.md`: roteiro passo-a-passo da demo.

### Aluno 2 — SaaS Backend
- [ ] Prometheus via `prometheus-fastapi-instrumentator`: latência (histogram), taxa de erro (counter), throughput (gauge) em `/metrics`.
- [ ] Logs estruturados JSON com `structlog`: `timestamp`, `level`, `correlation_id`, `service`, `message`.
- [ ] Middleware propagando `X-Correlation-ID` para gRPC, REST e logs.
- [ ] Headers de segurança em todas as respostas: `HSTS`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, CORS restrito ao domínio do frontend.
- [ ] OpenAPI 3.0 final publicado em `/docs` (Swagger UI acessível publicamente).
- [ ] Script `deploy.sh` ou GitHub Actions para deploy automatizado: build → push ECR → restart.

### Aluno 3 — Client Agent + IoT
- [ ] Métricas do Motor de Regras: `rules_evaluated_total`, `rule_latency_seconds`, `alerts_triggered_total` (formato Prometheus).
- [ ] Monitoramento MQTT Broker: conexões ativas, `messages_received`, `messages_sent`.
- [ ] Teste de carga final: 10.000 mensagens MQTT → medir latência sensor→dashboard. Meta: ≤ 2s (RNF-003).
- [ ] `docs/ARCHITECTURE.md` com diagrama final do sistema.
- [ ] `docs/DR.md`: procedimento de failover e recuperação de desastres.

**Critérios de Aceitação S8 (MVP Completo):**
- Demo ao vivo: sensor (simulador MQTT) → dado aparece no dashboard em ≤ 2s.
- Downlink funcional: botão no frontend → log do ChirpStack confirmando enfileiramento.
- Dois tenants distintos: isolamento comprovado (tenant A não vê dados do tenant B).
- Headers de segurança presentes em todas as respostas HTTP (`curl -I` comprovando).
- Correlation ID rastreável end-to-end nos logs.
- Teste de carga: 10k mensagens, latência média ≤ 2s, zero perdas.
- CI verde em todos os repositórios com badge no README.
- README de cada módulo: objetivo, stack, variáveis de ambiente, como subir localmente, como deployar.

---

## Dependências Críticas entre Alunos

| Dependência | Quem entrega | Quem depende | Prazo |
|:---|:---|:---|:---|
| Stub OpenAPI | Aluno 2 | Aluno 1 | 03/09 (S1) |
| Schema gRPC (`proto/`) | Aluno 2 + Aluno 3 | Ambos | 05/09 (S1) |
| Endpoint `POST /ingest` | Aluno 3 | Aluno 2 (roteamento) | 23/09 (S2) |
| WebSocket `/ws/telemetry/{app_id}` | Aluno 3 | Aluno 1 | 07/10 (S3) |
| Imagem Docker do tenant no ECR | Aluno 3 | Aluno 2 (provisionamento) | 21/10 (S4) |
| Endpoint `POST /auth/login` + JWT | Aluno 2 | Aluno 1 + Aluno 3 | 04/11 (S5) |
| Payload de regra definido | Aluno 3 | Aluno 1 (tela de regras) | 18/11 (S6) |

Antes das dependências estarem prontas: usar mocks locais. Nunca bloquear desenvolvimento por esperar outro aluno.

---

## Checklist do MVP por Sprint

- [ ] **S1:** Infra local, CI/CD, models, contratos definidos.
- [ ] **S2:** Dois serviços na AWS, gRPC funcionando, deploy real.
- [ ] **S3:** ChirpStack integrado, uplink ponta-a-ponta, WebSocket push.
- [ ] **S4:** Provisionamento automático de container por app, isolamento comprovado.
- [ ] **S5:** JWT/OAuth2, RBAC, TLS, mTLS, rate limiting.
- [ ] **S6:** Motor de regras, downlink, alertas Telegram/Email.
- [ ] **S7:** Circuit breaker, DLQ, retry, graceful shutdown.
- [ ] **S8:** Observabilidade, hardening, demo funcional, documentação final.

---

> **Regra do produto real:** se uma feature não tem teste e não está deployada, não existe. O código congela no dia **13/12 às 23:59**. O dia 14 é para apresentar.
