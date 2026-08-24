# Análise de Segurança do ChirpStack v4
## Catálogo de Camadas de Segurança Implementadas vs. Não Implementadas

**Data:** 25 de junho de 2026  
**Versão analisada:** ChirpStack v4.x  
**Fonte:** Documentação oficial (https://www.chirpstack.io/docs/), especificações LoRa Alliance, código-fonte e fórum da comunidade.

---

## 1. Visão Geral

O ChirpStack é um Network Server LoRaWAN open-source (licença MIT) que consolida em um único componente as funcionalidades de Network Server, Application Server e Join Server interno. Este documento cataloga **todas as camadas de segurança** que o ChirpStack implementa, as que implementa parcialmente e as que estão **faltando**, com referências às especificações da LoRa Alliance e boas práticas de indústria.

> **Nota importante:** O ChirpStack implementa as camadas **obrigatórias de protocolo LoRaWAN** (air interface), mas delega ao operador a configuração de muitas camadas de segurança de infraestrutura. Isso é consistente com sua natureza open-source — ele fornece os mecanismos, mas o hardening é responsabilidade de quem faz o deploy.

---

## 2. Legenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado nativamente |
| ⚠️ | Implementado parcialmente ou requer configuração manual |
| ❌ | Não implementado / Não documentado |
| 📋 | Requerido por especificação LoRa Alliance |
| 🏛️ | Requerido por regulamentação (ex: EU CRA, RED DA) |
| 📖 | Recomendado por boas práticas / ISO 27001 |

---

## 3. Camada 1: Segurança do Ar (Air Interface) — LoRaWAN Protocol

Esta camada é definida pela **LoRaWAN Specification** (v1.0.x, v1.0.4, v1.1) e pela **LoRa Alliance**.

### 3.1 Criptografia e Integridade

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 1.1 | **AES-128 Criptografia (MAC Layer)** | ✅ 📋 | Implementado conforme especificação LoRaWAN. O ChirpStack deriva e gerencia as chaves de sessão de rede (NwkSKey, FNwkSIntKey, SNwkSIntKey, NwkSEncKey). |
| 1.2 | **AES-128 Criptografia (Payload / AppSKey)** | ✅ 📋 | Implementado. O ChirpStack pode descriptografar o payload da aplicação no modo padrão (Join Server interno). |
| 1.3 | **MIC — Message Integrity Code (AES-CMAC)** | ✅ 📋 | Validado em todo uplink e downlink. Rejeita frames com MIC inválido. |
| 1.4 | **Frame Counter (32 bits)** | ✅ 📋 | Implementado desde v1.0.4. Proteção contra replay attacks via validação de contador de frames. |
| 1.5 | **DevNonce como contador (anti-replay join)** | ✅ 📋 | Implementado em v1.0.4+. O DevNonce é tratado como contador sequencial, não aleatório. |
| 1.6 | **Separação NwkKey / AppKey (LoRaWAN 1.1)** | ✅ 📋 | Suportado. ChirpStack distingue NwkKey (raiz de rede) e AppKey (raiz de aplicação) para dispositivos v1.1. |
| 1.7 | **Múltiplas chaves de sessão (v1.1)** | ✅ 📋 | Suportado: FNwkSIntKey, SNwkSIntKey, NwkSEncKey, AppSKey. |
| 1.8 | **OTAA — Over-The-Air Activation** | ✅ 📋 | Implementado como método padrão e recomendado de ativação. |
| 1.9 | **ABP — Activation By Personalization** | ✅ 📋 | Suportado, mas a documentação recomenda OTAA por ser mais seguro. |
| 1.10 | **Rejoin / Rekeying periódico (v1.1)** | ✅ 📋 | Suportado. Dispositivos v1.1 podem solicitar reativação periódica para renovar chaves e resetar frame counters. |
| 1.11 | **Relay Specification (TS011)** | ✅ 📋 | Suportado via device profiles. Inclui criptografia de relay com AES128-CMAC para integridade dos pacotes relayados. |

### 3.2 End-to-End Encryption (E2E) — Camada de Aplicação

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 2.1 | **End-to-End Encryption com Join Server externo** | ⚠️ 📋 | **Implementado, mas requer configuração avançada.** O ChirpStack pode operar com Join Server externo (ex: Semtech LoRa Cloud) onde o AppSKey é criptografado com KEK e nunca descriptografado pelo ChirpStack. Requer: (a) Join Server externo configurado, (b) KEK compartilhada entre Join Server e aplicação final. |
| 2.2 | **Key Encryption Keys (KEK)** | ✅ 📋 | Suportado via configuração em `chirpstack.toml`. Permite criptografar chaves de sessão entre Join Server ↔ Network Server e entre Network Servers em roaming. |
| 2.3 | **AppSKey inacessível ao Network Server (modo E2E)** | ⚠️ 📋 | **Possível, mas não é o padrão.** No modo padrão (Join Server interno), o ChirpStack DERIVA e POSSUI o AppSKey. Para isolá-lo, é obrigatório usar Join Server externo + KEK. |

### 3.3 Elementos de Segurança Física

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 3.1 | **Secure Elements (ATECC608A, TPM, etc.)** | ❌ 📋 | **NÃO implementado.** O ChirpStack não possui integração nativa com secure elements. O provisionamento de chaves em hardware seguro é delegado inteiramente ao processo de fabricação do dispositivo. O ChirpStack recebe apenas DevEUI e AppKey já configurados. |
| 3.2 | **HSM — Hardware Security Module** | ❌ 📖 | **NÃO documentado.** Não há suporte documentado para HSMs (ex: AWS CloudHSM, Thales Luna) para armazenamento seguro de root keys ou KEKs. |
| 3.3 | **Key Rotation automática** | ❌ 📖 | **NÃO implementado.** Não há mecanismo automático de rotação de AppKey/NwkKey. Rekeying depende de Rejoin (v1.1) ou reativação manual. |

---

## 4. Camada 2: Segurança de Transporte (Backend Communications)

Esta camada é definida pela **LoRaWAN Backend Interfaces Specification** (v1.0, v1.1).

### 4.1 TLS / HTTPS para APIs Backend

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 4.1 | **TLS 1.2+ para Backend Interfaces** | ✅ 📋 | Suportado para comunicação com Join Servers externos e roaming. Configurável via `ca_cert`, `tls_cert`, `tls_key` em `chirpstack.toml`. |
| 4.2 | **mTLS (Mutual TLS) para Backend Interfaces** | ✅ 📋 | Suportado. O ChirpStack pode apresentar certificado cliente ao se comunicar com Join Servers e roaming partners. |
| 4.3 | **IPsec VPN (alternativa ao TLS)** | ⚠️ 📋 | **Não implementado nativamente**, mas aceitável pela especificação. Deve ser configurado via infraestrutura de rede (roteadores, firewalls). |
| 4.4 | **Replay Protection (Backend)** | ✅ 📋 | Implementado via TLS e via mecanismos do protocolo Backend Interfaces. |
| 4.5 | **Integridade de mensagens (Backend)** | ✅ 📋 | Garantida pelo TLS e pela estrutura de mensagens do Backend Interfaces. |
| 4.6 | **DNSSEC / NAPTR para NetID/JoinEUI** | ⚠️ 📋 | **Parcial.** O ChirpStack suporta `resolve_join_eui_domain_suffix` e `resolve_net_id_domain_suffix` para resolução DNS, mas **não há menção a DNSSEC** na documentação. |

### 4.2 TLS para MQTT (Gateway ↔ Network Server)

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 4.7 | **TLS para MQTT (Gateway Bridge → Broker)** | ✅ 📖 | Suportado. Esquemas `ssl://` e `wss://` disponíveis. Configurável via `ca_cert`, `tls_cert`, `tls_key`. |
| 4.8 | **mTLS para Gateways (certificados cliente)** | ✅ 📖 | **Suportado e recomendado.** O ChirpStack pode gerar certificados de cliente automaticamente (CN = Gateway ID) quando configurado com CA cert + key. A documentação oficial fornece guia completo de configuração com Mosquitto. |
| 4.9 | **TLS para MQTT (Integração → Broker)** | ✅ 📖 | Suportado. A integração MQTT do ChirpStack pode usar `ssl://` com autenticação por certificado. |
| 4.10 | **TLS para MQTT (MQTT Forwarder → Broker)** | ✅ 📖 | Suportado. O ChirpStack MQTT Forwarder suporta `ssl://`, `wss://`, `ca_cert`, `tls_cert`, `tls_key`. |

### 4.3 TLS para Banco de Dados e Cache

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 4.11 | **TLS para PostgreSQL** | ✅ 📖 | Suportado. `sslmode` configurável: `disable`, `prefer`, `require`, `verify-ca`, `verify-full`. `ca_cert` opcional para certificados self-signed. |
| 4.12 | **TLS para Redis** | ✅ 📖 | Suportado via esquema `rediss://`. Autenticação por senha também suportada (`redis://:password@host:port`). |
| 4.13 | **TLS para Kafka (Integração)** | ✅ 📖 | Suportado. Flag `tls=true` na configuração de integração Kafka. |
| 4.14 | **TLS para AMQP/RabbitMQ (Integração)** | ⚠️ 📖 | **Não explicitamente documentado** na configuração de integração AMQP, mas geralmente suportado pelo protocolo AMQP. |

---

## 5. Camada 3: Segurança da Interface Web e API

### 5.1 Autenticação e Autorização

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 5.1 | **Autenticação de usuários (Web UI)** | ✅ 📖 | Implementado. Login com usuário/senha. Credenciais padrão `admin/admin` (⚠️ devem ser alteradas imediatamente). |
| 5.2 | **JWT para sessões Web** | ✅ 📖 | Implementado. Tokens JWT assinados com `api.secret` (deve ser gerado com `openssl rand -base64 32`). |
| 5.3 | **RBAC — Role-Based Access Control** | ✅ 📖 | Implementado. Hierarquia: Global Admin → Tenant Admin → Tenant Regular User. Controle de acesso por tenants, organizações, aplicações e dispositivos. |
| 5.4 | **OpenID Connect (OIDC)** | ✅ 📖 | Suportado como backend de autenticação alternativo. Integração com Keycloak, Auth0, Google, etc. |
| 5.5 | **OAuth2** | ✅ 📖 | Suportado (ex: Clerk). Configurável em `user_authentication.oauth2`. |
| 5.6 | **API Keys (gRPC)** | ✅ 📖 | Implementado. Long-lived tokens JWT para automação. Criáveis via CLI (`chirpstack create-api-key`) ou Web UI. |
| 5.7 | **Escopos de API Keys (Global vs. Tenant)** | ✅ 📖 | Suportado. API keys globais (admin) e por tenant (limitadas). |
| 5.8 | **Revogação de API Keys** | ✅ 📖 | Suportado via interface web. Alterar `api.secret` invalida TODOS os tokens existentes. |

### 5.2 Proteção da API

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 5.9 | **TLS para API gRPC** | ⚠️ 📖 | **Não documentado explicitamente** na configuração do ChirpStack. A API gRPC roda em HTTP/2 na porta 8080. TLS geralmente é terminado por um reverse proxy (nginx, traefik). |
| 5.10 | **Rate Limiting** | ❌ 📖 | **NÃO implementado.** Não há proteção nativa contra brute-force na API ou flooding. Deve ser implementado via reverse proxy. |
| 5.11 | **WAF / Proteção contra injeção** | ❌ 📖 | **NÃO implementado.** Sem firewall de aplicação web nativo. |
| 5.12 | **REST API embutida** | ❌ 📖 | **Removida no v4.** O servidor REST API é um componente separado (`chirpstack-rest-api`). A documentação recomenda usar gRPC diretamente. |
| 5.13 | **Audit Logging de acessos à API** | ❌ 📖 | **NÃO implementado.** Não há log detalhado de quem acessou qual endpoint da API e quando. |

---

## 6. Camada 4: Segurança da Infraestrutura Interna

### 6.1 Banco de Dados

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 6.1 | **PostgreSQL com TLS** | ✅ 📖 | Suportado. Ver item 4.11. |
| 6.2 | **Criptografia de dados em repouso (PostgreSQL)** | ❌ 🏛️ | **NÃO implementado pelo ChirpStack.** Depende da configuração do PostgreSQL (TDE, LUKS, etc.). |
| 6.3 | **Connection Pooling seguro** | ✅ 📖 | Suportado. `connection_recycling_method="verified"` recomendado para produção. |
| 6.4 | **SQLite (alternativa ao PostgreSQL)** | ✅ 📖 | Suportado em builds específicas. Menos robusto para produção. |

### 6.2 Cache e Mensageria

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 6.5 | **Redis com TLS** | ✅ 📖 | Suportado via `rediss://`. Ver item 4.12. |
| 6.6 | **Criptografia de dados em repouso (Redis)** | ❌ 🏛️ | **NÃO implementado pelo ChirpStack.** Depende da configuração do Redis. |
| 6.7 | **Redis Cluster** | ✅ 📖 | Suportado. Configurável via flag `cluster=true`. |
| 6.8 | **Key Prefix no Redis** | ✅ 📖 | Suportado. Útil para isolamento em multi-tenant ou múltiplos deployments. |
| 6.9 | **Mosquitto (MQTT Broker) com TLS** | ✅ 📖 | Suportado. O Docker Compose oficial inclui Mosquitto. Guia oficial de configuração TLS disponível. |
| 6.10 | **ACL no MQTT Broker baseada em certificados** | ✅ 📖 | Suportado. Documentação oficial demonstra ACL com `use_identity_as_username=true` e CN do certificado. |

### 6.3 Container / Deployment

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 6.11 | **Docker Compose oficial** | ✅ 📖 | Disponível em `chirpstack/chirpstack-docker`. **Nota:** documentado como "ponto de partida para testes", não para produção. |
| 6.12 | **Docker Secrets** | ❌ 📖 | **NÃO documentado.** O ChirpStack v4 usa substituição de variáveis de ambiente dentro do TOML (`${VAR}`), mas não há integração nativa com Docker Secrets. |
| 6.13 | **Network Isolation (Docker)** | ❌ 📖 | **NÃO configurado por padrão.** O Docker Compose oficial usa bridge padrão. Recomenda-se criar networks customizadas. |
| 6.14 | **Read-only containers** | ❌ 📖 | **NÃO documentado.** Não há instruções para rodar containers em modo read-only. |
| 6.15 | **Non-root containers** | ❌ 📖 | **NÃO documentado.** As imagens Docker oficiais rodam como root por padrão. |

---

## 7. Camada 5: Segurança de Gateways

### 7.1 Autenticação e Autorização de Gateways

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 7.1 | **Gateway ID / EUI como identificador** | ✅ 📋 | Implementado. O Gateway EUI (64 bits) é usado como identificador único. |
| 7.2 | **Registro obrigatório de gateways** | ✅ 📋 | Implementado. `allow_unknown_gateways=false` (padrão) rejeita uplinks de gateways não registrados. |
| 7.3 | **Autenticação de gateways por mTLS** | ✅ 📖 | Suportado. O ChirpStack pode gerar certificados de cliente com CN = Gateway ID. |
| 7.4 | **Autenticação de gateways por username/password (MQTT)** | ✅ 📖 | Suportado. Configurável no Gateway Bridge e MQTT Forwarder. |
| 7.5 | **Tenant isolation de gateways** | ⚠️ 📖 | **Parcial.** Gateways pertencem a tenants, mas a **conectividade é compartilhada** em toda a rede. Um tenant pode ver dados de dispositivos de outros tenants se passarem por seu gateway. |
| 7.6 | **Force gateways as private** | ✅ 📖 | Suportado via `force_gws_private=true` no device profile. Restringe gateways a dispositivos do mesmo tenant. |

### 7.2 Protocolos de Gateway

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 7.7 | **Basics Station com TLS (wss://)** | ✅ 📋 | Suportado. Gateway Bridge pode escutar em WebSocket seguro com `tls_cert` e `tls_key`. Suporta validação de certificado de gateway via `ca_cert`. |
| 7.8 | **Semtech UDP Packet Forwarder** | ✅ 📋 | Suportado, mas **sem criptografia nativa**. A documentação recomenda deploy do Gateway Bridge **no próprio gateway** para que o tráfego UDP fique local. |
| 7.9 | **ChirpStack Concentratord** | ✅ 📋 | Suportado. Comunicação via IPC (Unix domain sockets) — seguro para deploy local no gateway. |
| 7.10 | **CUPS — Configuration and Update Server** | ❌ 📋 | **NÃO implementado.** A documentação de configuração de gateways instrui explicitamente: "ChirpStack does not provide a CUPS endpoint". |
| 7.11 | **FUOTA para gateways** | ❌ 📋 | **NÃO implementado para gateways.** FUOTA é suportado apenas para dispositivos finais. Atualização de firmware de gateway é manual ou via ChirpStack Gateway OS. |

---

## 8. Camada 6: Segurança de Dispositivos

### 8.1 Validação e Autenticação

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 8.1 | **Validação de DevEUI** | ✅ 📋 | Implementado. DevEUI é o identificador único do dispositivo no banco de dados. |
| 8.2 | **Validação de JoinEUI** | ✅ 📋 | Implementado. Usado para roteamento ao Join Server correto. |
| 8.3 | **Validação de MIC em uplinks** | ✅ 📋 | Implementado. Frames com MIC inválido são descartados. |
| 8.4 | **Validação de frame counter** | ✅ 📋 | Implementado. Uplinks com frame counter menor ou igual ao último válido são rejeitados. |
| 8.5 | **Frame counter validation desabilitável** | ⚠️ 📋 | **Implementado, mas é uma vulnerabilidade.** Pode ser desabilitado por dispositivo via Web UI. A documentação exibe aviso explícito: "disabling the frame-counter validation will compromise security as it allows replay-attacks". |
| 8.6 | **ABP com frame counter persistente** | ✅ 📋 | Implementado. Frame counters de dispositivos ABP são persistidos no banco de dados. |
| 8.7 | **Device Profiles com restrições de segurança** | ✅ 📋 | Implementado. O device profile define MAC version, regional parameters, classe do dispositivo, etc. |

### 8.2 Logging e Monitoramento de Segurança

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 8.8 | **Frame Logging (uplink/downlink)** | ✅ 📖 | Implementado. Redis Streams armazenam frames de todos os gateways e dispositivos. Inclui frames que falharam na validação de MIC e frame counter (útil para detecção de ataques). |
| 8.9 | **Event Logging** | ✅ 📖 | Implementado. Redis Streams para eventos de dispositivos (join, uplink, downlink, ack, error, etc.). |
| 8.10 | **Per-device frame/event logs** | ✅ 📖 | Implementado. Streams separados por dispositivo com TTL configurável. |
| 8.11 | **Prometheus Metrics** | ✅ 📖 | Implementado. Endpoint `/metrics` para monitoramento de saúde e métricas de segurança. |
| 8.12 | **Health Check endpoint** | ✅ 📖 | Implementado. Endpoint `/health` para verificação de saúde do sistema. |
| 8.13 | **Alertas automáticos de segurança** | ❌ 📖 | **NÃO implementado.** Não há detecção automática de anomalias, brute-force, ou replay attacks. |
| 8.14 | **SIEM integration** | ❌ 📖 | **NÃO implementado.** Logs não são exportados em formato padronizado para SIEM. |

---

## 9. Camada 7: Funcionalidades Avançadas e Específicas

### 9.1 Roaming

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 9.1 | **Passive Roaming (Backend Interfaces)** | ✅ 📋 | Implementado. Suporta acordos de roaming passivo via Backend Interfaces API. |
| 9.2 | **Roaming com KEK** | ✅ 📋 | Suportado. `passive_roaming_kek_label` criptografa chaves de sessão durante o roaming. |
| 9.3 | **Roaming com validação de MIC** | ✅ 📋 | Suportado. `passive_roaming_validate_mic` permite validar MIC durante o roaming. |
| 9.4 | **Roaming ativo (handover)** | ❌ 📋 | **NÃO implementado.** Apenas passive roaming é suportado. |

### 9.2 Multicast e FUOTA

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 9.5 | **Multicast (Class-B e Class-C)** | ✅ 📋 | Implementado. Suporta grupos multicast com chaves de sessão multicast (McAppSKey, McNwkSKey). |
| 9.6 | **FUOTA — Firmware Update Over-The-Air** | ✅ 📋 | Implementado. Segue especificações LoRa Alliance: Clock Sync, Fragmented Data Block Transport, Remote Multicast Setup. |
| 9.7 | **Criptografia de firmware FUOTA** | ✅ 📋 | Implementado. O firmware é criptografado e transmitido via multicast seguro. |

### 9.3 Codec e Payload Processing

| # | Requisito | Status | Detalhes |
|---|-----------|--------|----------|
| 9.8 | **JavaScript Codec (QuickJS)** | ✅ 📋 | Implementado. Ambiente sandboxed com limite de execução (`max_execution_time`). |
| 9.9 | **Cayenne LPP Codec** | ✅ 📋 | Implementado nativamente. |
| 9.10 | **Sandboxing de código JavaScript** | ⚠️ 📖 | **Parcial.** QuickJS fornece isolamento básico, mas não há menção a seccomp, namespaces, ou containers para execução de codecs. |

---

## 10. Resumo Executivo

### 10.1 Pontos Fortes (✅ Implementados)

1. **Conformidade completa com a especificação LoRaWAN** — AES-128, MIC, frame counters, OTAA, ABP, v1.1 keys
2. **Suporte a Join Server externo** — Permite arquitetura E2E onde ChirpStack não acessa AppSKey
3. **TLS/mTLS abrangente** — Suportado em MQTT, Backend Interfaces, PostgreSQL, Redis
4. **RBAC granular** — Modelo de tenants com controle de acesso hierárquico
5. **Autenticação flexível** — Internal, OpenID Connect, OAuth2
6. **Frame logging completo** — Inclui frames rejeitados (útil para forense)
7. **Roaming passivo** — Com KEK e validação de MIC
8. **FUOTA seguro** — Multicast criptografado para updates de firmware
9. **Código aberto auditable** — MIT license permite auditoria independente

### 10.2 Pontos Fracos e Lacunas (❌ Não Implementados)

1. **CUPS não suportado** — Provisionamento automático de gateways não existe
2. **Sem rate limiting** — API vulnerável a brute-force e flooding
3. **Sem WAF / proteção de aplicação** — Sem firewall de aplicação web
4. **Sem secure elements / HSM** — Chaves armazenadas em software (PostgreSQL/Redis)
5. **Sem criptografia de dados em repouso** — Depende do DBA configurar TDE/LUKS
6. **Sem auditoria de acesso à API** — Não há log de quem acessou qual endpoint
7. **Sem detecção de anomalias / IDS** — Não há alertas automáticos de segurança
8. **Sem key rotation automática** — Rekeying manual ou via Rejoin (v1.1)
9. **Sem certificação formal da LoRa Alliance** — Não há programa de certificação para Network Servers
10. **Docker Compose não hardenizado** — Imagem de testes, não produção

### 10.3 Itens Parciais (⚠️ Requerem Configuração Manual)

1. **End-to-End Encryption** — Possível, mas requer Join Server externo + KEK
2. **TLS para API gRPC** — Geralmente terminado por reverse proxy
3. **DNSSEC** — Suporta resolução DNS, mas não há menção a DNSSEC
4. **Frame counter disable** — Pode ser desabilitado por dispositivo (risco de segurança)
5. **Gateway tenant isolation** — Gateways são compartilhados na rede
6. **Sandboxing de codecs** — QuickJS básico, sem isolamento de sistema operacional

---

## 11. Recomendações para Deploy Seguro

### 11.1 Checklist de Hardening Obrigatório

```
□ Alterar senha padrão admin/admin imediatamente
□ Gerar api.secret forte (openssl rand -base64 32)
□ Habilitar TLS em TODAS as comunicações MQTT (ssl://)
□ Configurar mTLS para gateways (certificados cliente)
□ Configurar TLS para PostgreSQL (sslmode=require)
□ Configurar TLS para Redis (rediss://)
□ Usar Basics Station (wss://) em vez de Semtech UDP
□ Manter allow_unknown_gateways=false
□ Manter frame counter validation habilitado (não desabilitar)
□ Criar API keys para automação (não usar login JWT)
□ Configurar reverse proxy (nginx/traefik) com TLS para API web
□ Implementar rate limiting no reverse proxy
□ Isolar redes Docker (networks customizadas)
□ Configurar firewall para restringir portas expostas
□ Fazer backup regular do PostgreSQL
□ Monitorar frame logs para anomalias
□ (Opcional) Configurar Join Server externo para E2E encryption
□ (Opcional) Configurar KEKs para criptografia de chaves de sessão
□ (Opcional) Usar HSM para armazenamento de root keys
```

### 11.2 Para Ambientes de Missão Crítica

Se o deploy exige **conformidade regulatória** (EU CRA, ISO 27001, HIPAA, PCI-DSS), considere:

- **Adicionar um WAF** (CloudFlare, AWS WAF, ModSecurity)
- **Implementar SIEM** (Splunk, ELK, Grafana Loki) para centralizar logs
- **Usar HSM** para proteger AppKey/NwkKey e KEKs
- **Configurar criptografia de dados em repouso** no PostgreSQL (TDE) e Redis
- **Implementar network policies** (Kubernetes) ou VLANs (on-premise)
- **Considerar soluções comerciais** (The Things Stack Enterprise, Actility) se o budget permitir

---

## 12. Referências

1. **Documentação oficial ChirpStack:** https://www.chirpstack.io/docs/
2. **LoRaWAN Specification v1.1** — LoRa Alliance
3. **LoRaWAN Backend Interfaces v1.0** — LoRa Alliance
4. **LoRaWAN Security Whitepaper** — LoRa Alliance
5. **Semtech Blog:** Enterprise-Grade LoRaWAN Security
6. **NCC Group:** Securing LoRaWAN Networks
7. **PMC Paper:** Analysis of LoRaWAN 1.0 and 1.1 Protocols Security
8. **Repositório GitHub:** https://github.com/chirpstack/chirpstack
9. **Docker Compose oficial:** https://github.com/chirpstack/chirpstack-docker
10. **Fórum da comunidade:** https://forum.chirpstack.io/

---

*Documento gerado em 25 de junho de 2026 com base na documentação oficial do ChirpStack e especificações da LoRa Alliance.*
