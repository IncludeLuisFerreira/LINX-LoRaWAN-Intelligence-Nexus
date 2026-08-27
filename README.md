# LINX — LoRaWAN Intelligence Nexus

![Platform](https://img.shields.io/badge/platform-AWS%20Cloud-orange)
![LoRaWAN](https://img.shields.io/badge/radio-LoRaWAN%20AU915-blue)
![ChirpStack](https://img.shields.io/badge/network-ChirpStack%20v4-purple)
![Docker](https://img.shields.io/badge/infra-Docker%20Compose-2496ED)

## Visão Geral

LINX é uma plataforma SaaS IoT distribuída para aquisição, processamento e visualização de dados de dispositivos LoRaWAN. A arquitetura é 100% cloud-native (AWS), com isolamento por aplicação: cada cliente recebe um ambiente Docker dedicado na nuvem com banco de dados e motor de regras próprios.

A conectividade LoRaWAN é provida pela rede de Gateways operada pela própria startup — o cliente instala apenas os sensores.

**Subsistemas:**

- `saas_backend/` — Core da plataforma: gerencia Organizações, Aplicações e Usuários; integra com ChirpStack/MQTT; orquestra provisionamento de contêineres por cliente.
- `client_agent_api/` — Middleware de segurança e roteamento: valida JWT e direciona requisições ao contêiner isolado correto.
- `tenant_app_template/` — Template do ambiente isolado de cada aplicação (motor de regras + TimescaleDB).
- `frontend/` — Dashboard React consumindo dados via `client_agent_api` e WebSocket.
- `infrastructure/` — Stack ChirpStack v4 dockerizada (Network Server, Gateway Bridge, MQTT, PostgreSQL).

> Documentação completa do produto: [`PRD_PLATAFORMA_IOT.md`](PRD_PLATAFORMA_IOT.md)

---

## Estrutura do Repositório

```
LINX/
├── saas_backend/           # Core SaaS: orquestração, MQTT, gRPC, API REST
├── client_agent_api/       # Middleware: autenticação JWT + roteamento multi-tenant
├── tenant_app_template/    # Template do Docker Cliente (motor de regras + TimescaleDB)
├── frontend/               # Dashboard web (React + Vite + TailwindCSS)
├── infrastructure/         # ChirpStack v4 + MQTT + PostgreSQL (Docker Compose)
│   ├── docker-compose.yml
│   └── configuration/      # chirpstack, gateway-bridge, mosquitto, postgresql
├── docs/
│   ├── estrutura_de_pastas/
│   ├── analise_seguranca_chirpstack/
│   └── manuais_de_config_e_impl/
├── PRD_PLATAFORMA_IOT.md
└── README.md
```

---

## Quickstart — Subindo o Network Server (ChirpStack)

O ChirpStack é a base de toda a infraestrutura LoRaWAN. Siga estes passos para colocá-lo no ar localmente.

### Pré-requisitos

- Docker e Docker Compose instalados
- Portas `8080` (ChirpStack UI), `1700/udp` (Gateway Bridge) e `1883` (MQTT) livres

### 1. Subir os serviços

```bash
cd infrastructure
docker compose up -d
```

Verifique se todos os contêineres estão saudáveis:

```bash
docker compose ps
```

Acesse a UI em `http://localhost:8080` — login: `admin` / senha: `admin`.

#### Referência: `docker-compose.yml`

O compose sobe os seguintes serviços:

```yaml
services:
  chirpstack:
    image: chirpstack/chirpstack:4
    command: -c /etc/chirpstack
    restart: unless-stopped
    volumes:
      - ./configuration/chirpstack:/etc/chirpstack
    depends_on:
      - postgres
      - mosquitto
      - redis
    environment:
      - MQTT_BROKER_HOST=mosquitto
      - REDIS_HOST=redis
      - POSTGRESQL_HOST=postgres
    ports:
      - "8080:8080"

  chirpstack-gateway-bridge:
    image: chirpstack/chirpstack-gateway-bridge:4
    restart: unless-stopped
    ports:
      - "1700:1700/udp"
    volumes:
      - ./configuration/chirpstack-gateway-bridge:/etc/chirpstack-gateway-bridge
    environment:
      - INTEGRATION__MQTT__EVENT_TOPIC_TEMPLATE=au915_0/gateway/{{ .GatewayID }}/event/{{ .EventType }}
      - INTEGRATION__MQTT__STATE_TOPIC_TEMPLATE=au915_0/gateway/{{ .GatewayID }}/state/{{ .StateType }}
      - INTEGRATION__MQTT__COMMAND_TOPIC_TEMPLATE=au915_0/gateway/{{ .GatewayID }}/command/#
    depends_on:
      - mosquitto

  chirpstack-rest-api:
    image: chirpstack/chirpstack-rest-api:4
    restart: unless-stopped
    command: --server chirpstack:8080 --bind 0.0.0.0:8090 --insecure
    ports:
      - "8090:8090"
    depends_on:
      - chirpstack

  postgres:
    image: postgres:14-alpine
    restart: unless-stopped
    volumes:
      - ./configuration/postgresql/initdb:/docker-entrypoint-initdb.d
      - postgresqldata:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=chirpstack
      - POSTGRES_PASSWORD=chirpstack
      - POSTGRES_DB=chirpstack

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --save 300 1 --save 60 100 --appendonly no
    volumes:
      - redisdata:/data

  mosquitto:
    image: eclipse-mosquitto:2
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./configuration/mosquitto/config/:/mosquitto/config/

volumes:
  postgresqldata:
  redisdata:
```

> Os topic templates do gateway bridge usam o prefixo `au915_0` (região AU915).

#### Referência: `configuration/chirpstack/chirpstack.toml`

```toml
[logging]
  level="info"

[postgresql]
  dsn="postgres://chirpstack:chirpstack@$POSTGRESQL_HOST/chirpstack?sslmode=disable"

[redis]
  servers=["redis://$REDIS_HOST/"]

[network]
  net_id="000000"
  enabled_regions=[
    "as923", "as923_2", "as923_3", "as923_4",
    "au915_0",
    "cn470_10", "cn779", "eu433", "eu868",
    "in865", "ism2400", "kr920", "ru864",
    "us915_0", "us915_1",
  ]

[api]
  bind="0.0.0.0:8080"
  secret="you-must-replace-this"

[integration]
  enabled=["mqtt"]
  [integration.mqtt]
    server="tcp://$MQTT_BROKER_HOST:1883/"
    json=true

[gateway.backend]
  type="mqtt"
  [gateway.backend.mqtt]
    server="tcp://$MQTT_BROKER_HOST:1883/"
    event_topic_prefix="au915_1"
    command_topic_prefix="au915_1"
```

#### Referência: `configuration/chirpstack/region_au915_0.toml`

Copiado de `region_au915_0.toml.example` (parte do repositório oficial ChirpStack Docker). Contém as configurações de canal, potência, SF e duty cycle para a banda AU915.

> **Ajuste para gateway monocanal (OTAA):** em `[regions.network]` force o servidor a responder somente na RX1 em 916,8 MHz/SF7 — combinação que o gateway monocanal consegue transmitir:
> `rx_window=1`, `enabled_uplink_channels=[8]`, `rx2_dr=5`, `rx2_frequency=916800000`, `adr_disabled=true`, `min_dr=5`, `max_dr=5`.

### 2. Criar o Gateway Profile

1. Navegue até **Gateways → Gateway Profiles → Add**
2. Nome: `Meu-Gateway`
3. Region: `au915_0`
4. Salve.

### 3. Criar o Device Profile

1. **Device Profiles → Add**
2. Nome: `Meu-EndDevice`
3. Region: `au915_0`
4. MAC version: `LoRaWAN 1.0.3` / Revision: `B`
5. Supports OTA: **marcado**
6. ADR: **desabilitado**
7. Salve.

### 4. Registrar um dispositivo (OTAA)

1. **Devices → Add**
2. Selecione o Device Profile criado acima.
3. Preencha DevEUI, AppEUI e AppKey com os mesmos valores do firmware do sensor.
4. Salve — o ChirpStack aguardará o Join Request do dispositivo.

> Em OTAA **não** há DevAddr/NwkSKey/AppSKey fixos no ChirpStack — eles são derivados pelo servidor no momento do join. Deixe **Disable frame-counter validation** desmarcado.

### 5. Verificar uplinks

| Onde | O que deve aparecer |
|------|---------------------|
| ChirpStack → Gateways | Gateway listado como "online" |
| ChirpStack → Devices → Events | Payload dos uplinks recebidos |
| MQTT (`localhost:1883`) | Tópico `application/+/device/+/event/up` com telemetria |

---

### Problemas comuns

| Problema | Causa | Solução |
|----------|-------|---------|
| Gateway não conecta ao ChirpStack | IP do servidor errado na configuração do gateway | Verifique o IP da máquina com `ip a` e atualize a configuração do gateway |
| ChirpStack não recebe uplinks | Região do Gateway Profile ≠ região do `chirpstack.toml` | Use `au915_0` (ou sua região) em ambos |
| Frame counter mismatch | FCnt dessincronizado com o servidor | OTAA reinicia FCnt a cada join; se persistir, delete a sessão do device e reinicie o nó |
| Join nunca completa (OTAA) | Downlink do Join Accept fora de 916,8 MHz/SF7 | Em `region_au915_0.toml`: `rx_window=1`, `enabled_uplink_channels=[8]`, `min_dr=max_dr=5`, `adr_disabled=true` |
