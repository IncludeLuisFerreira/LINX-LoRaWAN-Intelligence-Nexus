# 📄 PRD — Plataforma SaaS IoT Multi-Tenant & Dashboard Dinâmico (Fase A)

## 1. Visão Geral & Arquitetura do Sistema

Evoluir a infraestrutura LoRaWAN existente para uma plataforma **SaaS Multi-Tenant plug-and-play**.

A plataforma atuará como uma camada superior de controle (React + Node.js). O ChirpStack v4 continuará rodando isolado no Docker como um **motor Headless** (sem cabeça), lidando estritamente com as camadas de rádio e rede LoRaWAN. O usuário final interagirá apenas com a interface SaaS, sem jamais ter acesso direto ao painel do ChirpStack.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             SUA PLATAFORMA (SaaS)                               │
│                                                                                 │
│   [ Cliente Final ] ──(Navegador)──> [ Frontend React (Vite + Tailwind) ]        │
│                                                   │                             │
│                                            (REST API / JWT)                     │
│                                                   ▼                             │
│                                      [ Backend Node.js / Express ]              │
└───────────────────────────────────────────────────┬─────────────────────────────┘
                                                    │
                      ┌─────────────────────────────┴─────────────────────────────┐
                      │                                                           │
          (API REST - Porta 8090)                                    (MQTT - Porta 1883)
        Provisionamento Silencioso                                Telemetria em Tempo Real
                      │                                                           │
                      ▼                                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    INFRAESTRUTURA DOCKER (MOTOR OCULTO / HEADLESS)              │
│                                                                                 │
│        [ ChirpStack v4 ] ───────────────────────────────> [ Mosquitto MQTT ]     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stack Tecnológica Definida

| Camada | Tecnologia | Função no Sistema |
|--------|-----------|-------------------|
| **Backend Runtime** | Node.js (v20+) + TypeScript | Servidor principal do SaaS e orquestração de negócios. |
| **Framework HTTP** | Express.js | Rotas da API REST, controle de middlewares e autenticação. |
| **Autenticação** | JWT (JSON Web Tokens) + Bcrypt | Sessão stateless e controle de acesso por `tenant_id`. |
| **Comunicação Real-Time** | Socket.io (v4) | Emissão de telemetria ao vivo para o dashboard do frontend. |
| **Cliente MQTT** | MQTT.js | Ingestão contínua de uplinks do Mosquitto com reconexão automática. |
| **Banco de Dados** | PostgreSQL (v15+) + TimescaleDB | Relacional (Tenants, Users, Layouts) + Hypertables (Telemetria). |
| **ORM / Data Access** | Prisma ORM | Migrations e queries tipadas com isolamento estrito por `tenant_id`. |
| **Frontend Runtime** | React (v18+) + Vite + TypeScript | Interface do usuário e renderização do dashboard. |
| **UI & Componentes** | Tailwind CSS + Shadcn UI | Design modular e suporte a temas Dark/Light. |
| **Gráficos** | Recharts | Renderização dos dados temporais com base no JSON do layout. |
| **Integração Externa** | ChirpStack REST API v4 (Porta 8090) | Provisionamento automático via Admin API Key (`CHIRPSTACK_API_KEY`). |

---

## 3. Fluxo Prático do Usuário & Provisionamento

### 3.1 Autenticação e Navegação

1. O usuário se cadastra/autentica na plataforma React via `/api/auth/login`.
2. O Backend Node.js valida as credenciais e devolve um token JWT contendo `user_id`, `tenant_id` e `role`.
3. Todas as requisições subsequentes utilizam o cabeçalho `Authorization: Bearer <JWT>`.

### 3.2 Onboarding e Cadastro de Dispositivo (Passo a Passo)

1. No Frontend React, o usuário clica em **"+ Cadastrar Dispositivo"** e digita o nome e o DevEUI do sensor.
2. O Frontend envia `POST /api/devices` para o Backend Node.js com o JWT.
3. O Backend Node.js realiza uma chamada HTTP em segundo plano para a REST API do ChirpStack (`http://chirpstack-rest-api:8090/api/devices`) utilizando a `CHIRPSTACK_API_KEY`:
   - **Ação:** Registra o dispositivo no ChirpStack sob a aplicação padrão da plataforma.
4. Ao receber resposta `200 OK` do ChirpStack, o Backend salva o dispositivo na tabela local `devices` associado ao `tenant_id` do usuário.
5. O Frontend exibe a confirmação ao usuário e adiciona o dispositivo à tela.

### 3.3 Fluxo de Telemetria

```
Dispositivo LoRaWAN envia dados → Gateway capta → ChirpStack processa
                                      ↓
ChirpStack publica o JSON no Mosquitto MQTT (application/+/device/+/event/up)
                                      ↓
Backend Node.js consome o tópico MQTT, busca a qual tenant_id pertence aquele dev_eui,
salva a leitura no TimescaleDB e emite a atualização via Socket.io para a sala tenant_<tenant_id>
```

---

## 4. Modelo de Dados Relacional & Isolamento (Multi-Tenant)

### 4.1 Isolamento de Banco de Dados: Discriminator Column (`tenant_id`)

Todas as tabelas possuem obrigatoriamente a chave estrangeira `tenant_id`.

```sql
-- 1. Tabela de Tenants (Organizações/Clientes)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Tabela de Usuários do SaaS
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'TENANT_ADMIN' CHECK (role IN ('SUPER_ADMIN', 'TENANT_ADMIN', 'VIEWER')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Mapeamento de Dispositivos (SaaS ↔ ChirpStack)
CREATE TABLE devices (
    dev_eui VARCHAR(16) PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    last_seen TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Templates/Layouts Dinâmicos dos Dashboards (JSON)
CREATE TABLE dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title VARCHAR(100) DEFAULT 'Visão Geral',
    layout_config JSONB NOT NULL,
    is_default BOOLEAN DEFAULT true,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Telemetria em Séries Temporais (TimescaleDB)
CREATE TABLE telemetry_data (
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    dev_eui VARCHAR(16) NOT NULL,
    tenant_id UUID NOT NULL,
    payload JSONB NOT NULL
);

SELECT create_hypertable('telemetry_data', 'time');
```

---

## 5. Engine de Dashboard Dinâmico (JSON Schema)

O Frontend React não terá páginas codificadas rigidamente por sensor. Ele utilizará o componente `<DashboardRenderer/>` que lê o atributo `layout_config` do banco e renderiza os widgets dinamicamente.

### 5.1 Template JSON Padrão (Criado automaticamente no Onboarding do Tenant)

```json
{
  "gridColumns": 12,
  "widgets": [
    {
      "id": "card_ldr_1",
      "type": "STAT_CARD",
      "title": "Nível de Luminosidade",
      "metricPath": "ldr",
      "unit": "ADC",
      "layout": { "x": 0, "y": 0, "w": 6, "h": 2 }
    },
    {
      "id": "card_bat_1",
      "type": "STAT_CARD",
      "title": "Bateria do Nó",
      "metricPath": "v_bat",
      "unit": "mV",
      "layout": { "x": 6, "y": 0, "w": 6, "h": 2 }
    },
    {
      "id": "chart_telemetry_1",
      "type": "LINE_CHART",
      "title": "Histórico de Luminosidade",
      "metricPath": "ldr",
      "timeRange": "24h",
      "layout": { "x": 0, "y": 2, "w": 12, "h": 4 }
    }
  ]
}
```

---

## 6. Requisitos Funcionais (RFs) e Não-Funcionais (RNFs)

### Requisitos Funcionais (RFs)

| ID | Descrição |
|----|-----------|
| **RF01** | **Autenticação Isolada (JWT):** O sistema deve autenticar usuários e garantir que todas as queries filtrem estritamente por `tenant_id`. |
| **RF02** | **Provisionamento Transparente:** O cadastro de um novo dispositivo deve invocar silenciosamente a API REST do ChirpStack (porta 8090) usando a `CHIRPSTACK_API_KEY` do ambiente. |
| **RF03** | **Ingestão e Mapeamento MQTT:** O worker backend deve consumir a fila MQTT do ChirpStack, resolver o `tenant_id` correspondente ao `dev_eui` e gravar os dados de telemetria no TimescaleDB. |
| **RF04** | **Renderização Dinâmica:** O Frontend React deve ler o JSON de layout do tenant e montar os componentes visuais sem requerer novas compilações/deploys. |
| **RF05** | **Template Padrão de Boas-Vindas:** Ao registrar um novo tenant, o sistema deve instanciar automaticamente o dashboard padrão com suporte aos dados de LDR e Bateria já implementados no firmware do End Device. |

### Requisitos Não-Funcionais (RNFs)

| ID | Descrição |
|----|-----------|
| **RNF01** | **Transparência do Engine:** O painel/URL do ChirpStack (porta 8080) deve permanecer bloqueado para acesso externo, acessível apenas localmente ou via rede interna do Docker. |
| **RNF02** | **Desempenho de Telemetria:** O tempo entre a publicação do pacote pelo ChirpStack no Mosquitto e a atualização da tela via Socket.io não deve exceder 100ms. |
| **RNF03** | **Resiliência de Ingestão:** Se o banco de dados temporariamente falhar, o serviço MQTT do Backend deve reter os pacotes em memória buffer sem perder conexões com o broker. |

---

## 7. Cronograma de Execução Atualizado (Fase A)

### Etapa 1 Estruturação Multi-Tenant & Autenticação
- Criar Migrations no Prisma (Tenants, Users, Devices, Dashboards)
- Implementar serviços de Auth (JWT, Register, Login)
- Configurar variáveis de ambiente e token do ChirpStack (`CHIRPSTACK_API_KEY`)

### Etapa 2 Serviço de Integração ChirpStack & Ingestão MQTT
- Criar módulo HTTP Axios para falar com ChirpStack REST API (porta 8090)
- Atualizar cliente MQTT no backend para resolver e anexar `tenant_id` na ingestão

### Etapa 3 Engine de Dashboard Dinâmico no Frontend (React)
- Desenvolver componente `<DashboardRenderer />` baseado na árvore JSON
- Implementar widgets reativos: `<StatCardWidget />`, `<LineChartWidget />`
- Conectar Socket.io para atualizações em tempo real direcionadas por `tenant_id`

### Etapa 4 Teste de Campo & Validação de Ponta a Ponta
- Instalação do End Device em ambiente de teste real no campus IFSULDEMINAS
- Validação completa do fluxo: Firmware → Gateway → ChirpStack → SaaS Multi-Tenant

---