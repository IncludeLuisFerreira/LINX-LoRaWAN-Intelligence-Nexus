# LoRaWAN Project

![License](https://img.shields.io/badge/license-MIT-green)
![ESP32](https://img.shields.io/badge/platform-ESP32-blue)
![LoRa](https://img.shields.io/badge/radio-RFM95%20(SX1276)-orange)
![ChirpStack](https://img.shields.io/badge/network-ChirpStack%20v4-purple)
![AU915](https://img.shields.io/badge/band-AU915%20(916.8MHz)-red)
![Docker](https://img.shields.io/badge/infra-Docker%20Compose-2496ED)

## Visão Geral

Infraestrutura LoRaWAN completa e funcional, composta por quatro subsistemas integrados:

- **End Device** — Nó sensor ESP32 + RFM95 que coleta LDR, tensão da bateria, GPS e estado de botão, transmitindo via LoRaWAN Classe A (OTAA) a 916,8 MHz.
- **Gateway** — Gateway single-channel ESP32/ESP8266 + RFM95 com detecção CAD multi-SF, servidor web embarcado, OTA e protocolo Semtech UDP.
- **Network Server** — Pilha ChirpStack v4 dockerizada com PostgreSQL, Redis, Mosquitto MQTT e REST API.
- **IoT Dashboard** — Plataforma de monitoramento em tempo real ([`platform/`](platform/README.md)): consome os uplinks do broker MQTT, persiste em TimescaleDB, exibe cards/gráficos via WebSocket e dispara alertas por threshold com cooldown via Telegram e/ou E-mail.

O projeto opera na banda AU915 (916,8 MHz, canal 8).

## Guia de Reprodução

Este guia mostra o passo a passo exato para reproduzir esta infraestrutura do zero — desde o download de cada componente até o primeiro uplink chegar no ChirpStack.

---

### Tecnologias utilizadas

| Item | Especificação |
|------|---------------|
| Docker + Docker Compose | Linux (recomendado), macOS ou Windows c/ WSL2 |
| Arduino IDE | 2.x ou 1.8.x com suporte a ESP32 e ESP8266 |
| Placa 1 (gateway) | ESP32 ou ESP8266 + RFM95/SX1276 |
| Placa 2 (end device) | ESP32 + RFM95/SX1276 |
| Sensor | LDR (fotoresistor) + resistor 10kΩ (pull-down) |
| LED | Vermelho + resistor 220Ω (opcional) |
| Jumpers | Fêmea-fêmea, ~10 unidades |
| Fontes USB | 1 por placa |

---

### 1. Network Server — ChirpStack (Docker)

**Base:** [Repositório oficial ChirpStack Docker](https://github.com/chirpstack/chirpstack-docker)

```bash
git clone https://github.com/chirpstack/chirpstack-docker.git
cd infrastructure
```

#### 1.1 Estrutura de arquivos

Dentro de `infrastructure/` foram criados/modificados os seguintes arquivos:

##### `docker-compose.yml`

O conteúdo completo do `docker-compose.yml` utilizado é:

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
  
  chirpstack-gateway-bridge-basicstation:
    image: chirpstack/chirpstack-gateway-bridge:4
    restart: unless-stopped
    command: -c /etc/chirpstack-gateway-bridge/chirpstack-gateway-bridge-basicstation-au915_1.toml
    ports:
      - "3001:3001"
    volumes:
      - ./configuration/chirpstack-gateway-bridge:/etc/chirpstack-gateway-bridge
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

  webapp:
    build: ./app
    restart: unless-stopped
    ports:
      - "5000:5000"
    depends_on:
      - mosquitto

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

> **O que foi modificado em relação ao original:** ajuste nos topic templates do gateway bridge para usar o prefixo `au915_0` (região AU915), e adição do serviço `webapp` customizado.

##### `configuration/chirpstack/chirpstack.toml`

```toml
[logging]
  level="info"

[postgresql]
  dsn="postgres://chirpstack:chirpstack@$POSTGRESQL_HOST/chirpstack?sslmode=disable"
  max_open_connections=10
  min_idle_connections=0

[redis]
  servers=["redis://$REDIS_HOST/"]
  tls_enabled=false
  cluster=false

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
    clean_session=false
    qos=0
    client_id=""
    keep_alive="30s"
    tls_enabled=false
```

> **O que foi modificado:** `enabled_regions` inclui `au915_0`, e os topic prefixes do gateway backend foram alterados para `au915_1`.

 ##### `configuration/chirpstack/region_au915_0.toml`

Copiado de `region_au915_0.toml.example` (parte do repositório oficial). Contém as configurações de canal, potência, SF e duty cycle para a banda AU915.

> **Ajuste OTAA monocanal (migração ABP → OTAA):** em `[regions.network]` force o servidor a responder **somente na RX1 em 916,8 MHz/SF7** — combinação que o gateway monocanal consegue transmitir:
> `rx_window=1`, `enabled_uplink_channels=[8]`, `rx2_dr=5`, `rx2_frequency=916800000`, `adr_disabled=true`, `min_dr=5`, `max_dr=5`.

#### 1.2 Comandos executados

```bash
# Copiar configuração de região
cp configuration/chirpstack/region_au915_0.toml.example configuration/chirpstack/region_au915_0.toml

# Subir todos os serviços
docker compose up -d

# Verificar se subiu corretamente
docker compose ps
```

Acessar `http://localhost:8080` — login: `admin`, senha: `admin`.

#### 1.3 Criar Gateway Profile

1. **Gateways → Gateway Profiles → Add**
2. Nome: `Meu-Gateway`
3. Region: `au915_0`
4. **Save**

#### 1.4 Criar Device Profile

1. **Device Profiles → Add**
2. Nome: `Meu-EndDevice`
3. Region: `au915_0`
4. MAC version: `LoRaWAN 1.0.3`
5. Revision: `B`
6. Supports OTA: **marcado** (OTAA)
7. ADR: **desabilitado** (nó em canal único/SF fixo)
8. **Save**

---

### 2. Gateway — Single-Channel (ESP32/ESP8266 + RFM95)

**Base:** [ESP-Single-Channel-Gateway](https://github.com/Things4U/ESP-Single-Channel-Gateway) de Maarten Westenberg

```bash
git clone https://github.com/Things4U/ESP-Single-Channel-Gateway.git
```

#### 2.1 Wiring — Conexão RFM95 ↔ ESP32

| RFM95 | ESP32 |
|-------|-------|
| NSS   | GPIO 18 |
| SCK   | GPIO 5 |
| MOSI  | GPIO 27 |
| MISO  | GPIO 19 |
| DIO0  | GPIO 26 |
| DIO1  | GPIO 35 |
| DIO2  | GPIO 34 |
| RST   | GPIO 14 |
| 3.3V  | 3.3V |
| GND   | GND |

> Esta pinagem corresponde a `_PIN_OUT 4` (ESP32/TTGO) no código. Para ESP8266 Wemos ou Heltec, altere `_PIN_OUT` em `configGway.h` e verifique os pinos em `loraModem.h`.

#### 2.2 Arquivos modificados

##### `configGway.h` — Alterações necessárias

**Linha 91:** Habilitar banda AU915:
```c
// ANTES: (comentado ou com outra banda)
//#define EU863_870 1

// DEPOIS:
#define AU915_928 1
```

**Linha 106:** Definir protocolo Semtech UDP:
```c
// ANTES:
//#define _UDPROUTER 1

// DEPOIS:
#define _UDPROUTER 1
```

**Linha 121:** Spreading Factor padrão:
```c
// ANTES:
#define _SPREADING SF7
// (mantido)
```

**Linha 131:** CAD (Channel Activity Detection):
```c
// ANTES:
//#define _CAD 1

// DEPOIS:
#define _CAD 1
```

**Linha 171:** Pinagem da placa:
```c
// ANTES:
#define _PIN_OUT 4
// (mantido — 4 = ESP32 Heltec/TTGO)
```

**Linha 186:** Strict mode (canal único):
```c
// ANTES:
#define _STRICT_1CH 1
// (mantido)
```

**Linha 262:** Local server para decode:
```c
// ANTES:
#define _LOCALSERVER 1
// (mantido — permite decodificar pacotes localmente)
```

**Linha 294:** Lista de nós confiáveis:
```c
// ANTES:
#define _TRUSTED_NODES 1
// (mantido — exibe nomes amigáveis no servidor web)
```

**Linha 380:** IP do servidor ChirpStack — **obrigatório alterar**:
```c
// ANTES:
#define _TTNSERVER "router.eu.thethings.network"

// DEPOIS (substitua pelo IP da máquina do ChirpStack):
#define _TTNSERVER "192.168.1.198"
#define _TTNPORT 1700
```

> O IP `192.168.1.198` é um exemplo. Descubra o IP da máquina onde o ChirpStack está rodando com `ip a` ou `ifconfig`.

##### `configNode.h` — Criado a partir do template

Copie o template e edite com seus dados:

```bash
cp configNode.h.template configNode.h
```

**Rede Wi-Fi (obrigatório):**
```c
wpas wpa[] = {
    { "NOME_DA_SUA_REDE" , "SUA_SENHA" },
};
```

**Identificação do gateway:**
```c
#define _DESCRIPTION "Meu-Gateway-LoRa"
#define _EMAIL "meu@email.com"
#define _LAT -22.820923    // Sua latitude
#define _LON -47.066795    // Sua longitude
#define _ALT 625           // Sua altitude em metros
```

**(Opcional) Lista de nós conhecidos:**
```c
nodex nodes[] = {
    { 0x260417AD , "sensor-quarto" },
    { 0x260417AE , "sensor-quintal" },
};
```

##### `loraModem.h` — Frequências AU915

O arquivo já contém as definições para AU915 na seção `#ifdef AU915_928`. Verifique se as frequências estão corretas para sua região:

```c
#ifdef AU915_928
vector freqs[] = {
    { 916800000, 125, 7, 12, 916800000, 125, 7, 12 },  // Canal 0 - 916.8 MHz
    // ... demais canais
};
```

> No projeto, o gateway opera no canal 0 = 916,8 MHz, que é o canal 8 da sub-banda AU915.

#### 2.3 Upload

1. Abra `gateway.ino` na Arduino IDE.
2. **Ferramentas → Placa**: `ESP32 Dev Module` (ou `Wemos D1 R1` para ESP8266).
3. **Ferramentas → Porta**: selecione a porta USB do ESP.
4. **Upload** (CTRL+U).

> Após o upload, abra o Serial Monitor (115200 baud). O gateway exibirá "Connecting to WiFi...", o IP obtido, e em seguida "CAD start" — indicando que está escutando. Acesse o IP no navegador para o painel web.

---

### 3. End Device — Nó Sensor (ESP32 + RFM95 + LDR)

**Base:** Código próprio (escrito do zero), baseado na biblioteca [MCCI LoRaWAN LMIC](https://github.com/mcci-catena/arduino-lmic)

Não há um repositório upstream para clonar. Os arquivos foram criados manualmente.

#### 3.1 Wiring — Conexões

| RFM95 | ESP32 |
|-------|-------|
| NSS   | GPIO 18 |
| SCK   | GPIO 5 |
| MOSI  | GPIO 27 |
| MISO  | GPIO 19 |
| DIO0  | GPIO 26 |
| DIO1  | GPIO 35 |
| DIO2  | GPIO 34 |
| RST   | GPIO 14 |
| 3.3V  | 3.3V |
| GND   | GND |

| Componente | ESP32 |
|------------|-------|
| LDR (pino central) | GPIO 36 (ADC1_CH0) |
| LDR (GND) | GND |
| LDR (VCC) | 3.3V (via resistor 10kΩ) |
| LED vermelho (ânodo) | GPIO 4 (via resistor 220Ω) |
| LED vermelho (cátodo) | GND |
| LED amarelo (ânodo) | GPIO 2 (via resistor 220Ω) |
| LED amarelo (cátodo) | GND |
| LED verde (ânodo) | GPIO 15 (via resistor 220Ω) |
| LED verde (cátodo) | GND |
| Botão | GPIO 39 (VN) — GND quando pressionado |

#### 3.2 Instalar a biblioteca LMIC

Na Arduino IDE: **Ferramentas → Gerenciador de Bibliotecas** → procure por `MCCI LoRaWAN LMIC` → instale.

#### 3.3 Arquivos criados

Todos os arquivos abaixo foram criados dentro da pasta `firmware/end-device/`:

##### `lmic_project_config.h`

```c
#define CFG_sx1276_radio
#define CFG_au915
#define hal_init LMIC_hal_init
#define ARDUINO_LMIC_PROJECT_CONFIG_H_SUPPRESS_WARNING
```

> `CFG_sx1276_radio` para RFM95, `CFG_au915` para região AU915, `hal_init` renomeado para evitar conflito com a SDK do ESP32.

##### `config.h`

```c
#ifndef CONFIG_H
#define CONFIG_H

// Credenciais OTAA — arquivo NÃO versionado (ver .gitignore)
#include "nvs_secrets.h"

Preferences prefs;
#define NVS_NAMESPACE     "lorawan"
#define NVS_SLOT_COUNT    100
#define NVS_IDX_KEY       "fcnt_idx"
#define FCNT_SAVE_EVERY   10

static uint32_t fcntUp        = 0;
static uint32_t fcntSinceSave = 0;
static uint8_t  fcntSlotIdx   = 0;

#define TX_INTERVAL_MS  15000UL
#define TAMANHO_PACOTE 36
#define NUM_LEITURA_LDR 4

uint8_t Pacote_UL[TAMANHO_PACOTE];

// OTAA keys — lidas de nvs_secrets.h (DEVEUI/APPEUI LSB-first, APPKEY direto)
void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

#define OTAA_MAX_ATTEMPTS   5
#define OTAA_RETRY_DELAY_MS 30000UL

static osjob_t Envia_pkt_UL;
uint16_t PKT_UL = 0;
#define LORAWAN_FPORT   1

#endif
```

> As chaves OTAA (DevEUI, AppEUI, AppKey) ficam em `nvs_secrets.h`, que **não é versionado**. Gere-as com `openssl rand -hex 16` e cadastre os mesmos valores no ChirpStack.

##### `end-device.ino`

Arquivo principal com `setup()` e `loop()`:

```cpp
#include <Arduino.h>
#include <SPI.h>
#define LMIC_ENABLE_arbitrary_clock_error 1
#include <lmic.h>
#include <hal/hal.h>
#include <Preferences.h>
#include "config.h"

// Pinagem RFM95
#define SCK_PIN   5
#define MISO_PIN  19
#define MOSI_PIN  27
#define RST_PIN   14
#define NSS_PIN   18
#define DIO0_PIN  26
#define DIO1_PIN  35
#define DIO2_PIN  34

// Periféricos
#define LDR_PIN   36
#define BAT_PIN   32
#define BOTAO_PIN   39
#define LED_VERMELHO_PIN  4
#define LED_AMARELO_PIN  2
#define LED_VERDE_PIN  15

const int MY_ID = 3;
const int GATEWAY_ID = 0;
const int TIPO_SENSOR_LDR = 44;
const int TIPO_SENSOR_BAT = 11;
const int TIPO_SENSOR_GPS = 10;

#define LATITUDE  -22.820984
#define LONGITUDE -47.066727
#define ALTITUDE  625

// >>> As chaves OTAA ficam em nvs_secrets.h (NÃO versionado) <<<
// DevEUI = 07E32A82697444B9 | AppEUI = 0000000000000000
// AppKey = 1FD648EA9F3A1E2D014D8FF82C35683C
// >>> Cadastre os MESMOS valores no ChirpStack (Device -> OTAA) <<<

const lmic_pinmap lmic_pins = {
    .nss  = NSS_PIN,
    .rxtx = LMIC_UNUSED_PIN,
    .rst  = RST_PIN,
    .dio  = { DIO0_PIN, DIO1_PIN, DIO2_PIN },
};

void setup() {
    Serial.begin(115200);
    // ... inicialização de pinos, SPI, ADC, LMIC ...

    configura_camada_fisica();   // 1_PHY.ino
    configura_camada_rede();     // 3_NET.ino

    // OTAA: compensa o clock e dispara o Join Request.
    // A sessão é derivada do Join Accept — NÃO usar LMIC_setSession.
    LMIC_setClockError(MAX_CLOCK_ERROR * 1 / 100);
    LMIC_startJoining();

    configura_camada_transporte();  // 4_TRANSP.ino
    // O primeiro uplink é agendado em EV_JOINED (2_MAC.ino)
}

void loop() {
    os_runloop_once();
}
```

##### `1_PHY.ino` — Camada física

```cpp
#include "config.h"

void configura_camada_fisica() {
    for (int i = 0; i < 72; i++) {
        LMIC_disableChannel(i);
    }
    LMIC_enableChannel(8);   // AU915 canal 8 = 916,8 MHz
    LMIC_setDrTxpow(DR_SF7, 14);
    LMIC_setAdrMode(0);
    LMIC_setLinkCheckMode(0);
}

void PHY_Envia_UL(osjob_t* j) {
    if (LMIC.opmode & OP_JOINING) {   // OTAA: só envia após o join
        Serial.println(F("[TX] Ainda em JOINING — pulando uplink"));
        return;
    }
    if (LMIC.devaddr == 0) {
        Serial.println(F("[TX] Sem sessão ativa — pulando uplink"));
        return;
    }
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("[TX] Pendente — pulando este ciclo"));
        return;
    }
    digitalWrite(LED_VERMELHO_PIN, HIGH);
    APP_radio_send_UL();      // 5_APP.ino
    Transp_radio_send_UL();   // 4_TRANSP.ino
    NET_radio_send_UL();      // 3_NET.ino
    MAC_send_UL();            // 2_MAC.ino
    Pacote_UL[0] = 0;
    Pacote_UL[1] = 0;
    Pacote_UL[2] = 0;
    Pacote_UL[3] = 0;
    LMIC_setTxData2(1, Pacote_UL, sizeof(Pacote_UL), 0);
    Serial.println(F("[TX] Pacote Enviado"));
    digitalWrite(LED_VERMELHO_PIN, LOW);
}
```

> **Canal 8 = 916,8 MHz** é o padrão do projeto. Para outra região: EU868 canal 0 = 868,1 MHz; US915 canal 0 = 903,9 MHz.

##### `2_MAC.ino` — Camada MAC (frame counter, eventos)

```cpp
#include "config.h"

void MAC_send_UL(){
    Pacote_UL[4] = (fcntUp/256);
    Pacote_UL[5] = (fcntUp%256);
    Pacote_UL[6] = 0;
    Pacote_UL[7] = 0;
}

void onEvent(ev_t ev) {
    switch (ev) {
        case EV_JOINED:
            Serial.println(F("[LMIC] EV_JOINED"));
            fcntUp = 0; fcntSinceSave = 0;
            resetFrameCounterNVS();     // nova sessão OTAA -> FCnt 0
            configura_camada_fisica();  // reaplica canal único/SF7
            LMIC_setLinkCheckMode(0);
            os_setCallback(&Envia_pkt_UL, PHY_Envia_UL);
            break;

        case EV_JOIN_FAILED:
        case EV_REJOIN_FAILED:
            otaaAttempts++;
            os_setTimedCallback(&Envia_pkt_UL,
                os_getTime() + ms2osticks(OTAA_RETRY_DELAY_MS), OTAA_retry_join);
            break;

        case EV_TXCOMPLETE:
            Serial.println(F("[LMIC] EV_TXCOMPLETE"));
            fcntUp = LMIC.seqnoUp;
            fcntSinceSave++;
            if (fcntSinceSave >= FCNT_SAVE_EVERY) {
                saveFrameCounter(fcntUp + FCNT_SAVE_EVERY);
                fcntSinceSave = 0;
            }
            if (LMIC.txrxFlags & TXRX_ACK)
                Serial.println(F("  ACK recebido"));
            if (LMIC.dataLen)
                Serial.printf("  Downlink %d byte(s) na porta %d\n",
                              LMIC.dataLen, LMIC.frame[LMIC.dataBeg - 1]);
            os_setTimedCallback(&Envia_pkt_UL,
                os_getTime() + ms2osticks(TX_INTERVAL_MS), PHY_Envia_UL);
            break;
        default:
            break;
    }
}

void OTAA_retry_join(osjob_t* j) {
    if (otaaAttempts >= OTAA_MAX_ATTEMPTS) return;
    LMIC_reset();
    configura_camada_fisica();
    LMIC_startJoining();
}
```

##### `3_NET.ino` — Camada de rede

```cpp
#include "config.h"

void NET_radio_send_UL(){
    Pacote_UL[8] = GATEWAY_ID;
    Pacote_UL[9] = 0;
    Pacote_UL[10] = MY_ID;
    Pacote_UL[11] = 0;
}

void configura_camada_rede() {
    // OTAA: nenhuma sessão fixa. A sessão é derivada do Join Accept.
    // O join é disparado por LMIC_startJoining() no setup (.ino principal).
}
```

##### `4_TRANSP.ino` — Camada de transporte (NVS wear leveling)

```cpp
#include "config.h"

void Transp_radio_send_UL(){
    Pacote_UL[11] = 0;  // Downlink counter
    Pacote_UL[12] = 0;  // Uplink counter
}

void configura_camada_transporte() {
    // OTAA: nada de sessão fixa aqui. O FCnt é zerado em EV_JOINED
    // (resetFrameCounterNVS) e persistido com wear leveling conforme
    // os uplinks acontecem (ver onEvent em 2_MAC.ino).
}

void saveFrameCounter(uint32_t fcnt) {
    prefs.begin(NVS_NAMESPACE, false);
    fcntSlotIdx = (fcntSlotIdx + 1) % NVS_SLOT_COUNT;
    char key[10];
    snprintf(key, sizeof(key), "fcnt_%02d", fcntSlotIdx);
    prefs.putUInt(key, fcnt);
    prefs.putUChar(NVS_IDX_KEY, fcntSlotIdx);
    prefs.end();
}

void resetFrameCounterNVS() {
    prefs.begin(NVS_NAMESPACE, false);
    char key[10];
    for (int i = 0; i < NVS_SLOT_COUNT; i++) {
        snprintf(key, sizeof(key), "fcnt_%02d", i);
        prefs.remove(key);
    }
    prefs.remove(NVS_IDX_KEY);
    prefs.end();
    fcntUp = 0; fcntSinceSave = 0; fcntSlotIdx = 0;
}
```

##### `5_APP.ino` — Camada de aplicação (sensores)

```cpp
#include "config.h"

void APP_radio_send_UL(){
    // Leitura do LDR
    uint32_t soma = 0;
    for (int i = 0; i < NUM_LEITURA_LDR; i++) {
        soma += analogRead(LDR_PIN);
        delay(10);
    }
    uint16_t ldr = soma / NUM_LEITURA_LDR;

    Pacote_UL[0xD] = (ldr >> 8) & 0xFF;  // Inteiro LDR
    Pacote_UL[0xE] = ldr & 0xFF;          // Resto LDR
}
```

#### 3.4 Registrar o dispositivo no ChirpStack (OTAA)

1. Acesse `http://localhost:8080`
2. **Devices → Add**
3. Nome: `Meu-EndDevice`
4. Device Profile: selecione o criado no passo 1.4
5. **Activation**: selecione **OTAA**
6. Preencha com os MESMOS valores de `nvs_secrets.h`:
   - **DevEUI**: `07E32A82697444B9`
   - **AppEUI/JoinEUI**: `0000000000000000`
   - **AppKey**: `1FD648EA9F3A1E2D014D8FF82C35683C`
7. **Save**

> Em OTAA **não** há DevAddr/NwkSKey/AppSKey fixos no ChirpStack — eles são derivados pelo servidor no momento do join. Deixe **Disable frame-counter validation** desmarcado (a validação protege contra replay).

#### 3.5 Upload

1. Na Arduino IDE, abra `end-device.ino`
2. **Ferramentas → Placa**: `ESP32 Dev Module`
3. **Ferramentas → Porta**: selecione a porta USB do ESP32
4. **Upload** (CTRL+U)
5. Abra o Serial Monitor (115200 baud)

> Deve aparecer: `[LMIC] EV_JOINED` seguido de `[TX] Pacote Enviado` a cada 15 segundos.

---

### 4. Verificação — Sistema completo

Com todos os 3 componentes rodando:

| Onde olhar | O que deve aparecer |
|------------|---------------------|
| **Serial Monitor do end device** | `[LMIC] EV_JOINED` uma vez e depois `[TX] Pacote Enviado` a cada ~15s |
| **Serial Monitor do gateway** | `PUSH_DATA` com RSSI, SNR e payload do pacote |
| **ChirpStack → Gateways** | Gateway listado como "online", com uplinks recebidos |
| **ChirpStack → Devices → Events** | Payload hexa dos uplinks |
| **Navegador → IP do gateway** | Painel web com estatísticas de RX/TX |

#### Problemas comuns

| Problema | Causa | Solução |
|----------|-------|---------|
| Gateway não conecta ao ChirpStack | `_TTNSERVER` com IP errado | No PC do ChirpStack: `ip a` — use esse IP no `configGway.h` |
| End device não transmite | Canal errado para a região | Em `1_PHY.ino`, `LMIC_enableChannel(N)` — N depende da banda |
| ChirpStack não recebe uplinks | Região do Gateway Profile ≠ região do chirpstack.toml | Use `au915_0` (ou sua região) em ambos |
| Frame counter mismatch | FCnt dessincronizado com o servidor | OTAA reinicia FCnt a cada join; se persistir, delete a sessão do device e reinicie o nó |
| Join nunca completa (OTAA) | Downlink do Join Accept fora de 916,8 MHz/SF7 | Em `region_au915_0.toml`: `rx_window=1`, `enabled_uplink_channels=[8]`, `min_dr=max_dr=5`, `adr_disabled=true` |
| `EV_JOIN_FAILED` | Gateway monocanal não recebe/transmite a RX1 | Confira `_STRICT_1CH 1` e `_CHANNEL 0` (916,8 MHz) no `configGway.h`; reduza `_PULL_INTERVAL` se o downlink atrasar |
| Placa não compila | Faltou `lmic_project_config.h` | Coloque o arquivo na mesma pasta do .ino |
| Erro `hal_init` conflito | SDK do ESP32 vs LMIC | `#define hal_init LMIC_hal_init` em `lmic_project_config.h` |

---

### 5. IoT Dashboard — Monitoramento em tempo real

A plataforma [`platform/`](platform/README.md) adiciona
visualização e monitoramento em tempo real por cima do Network Server. Ela assina o
tópico `application/+/device/+/event/up` do Mosquitto, persiste as leituras num banco
PostgreSQL + TimescaleDB, transmite via WebSocket e notifica alertas por threshold.

```bash
cd platform
cp .env.example .env
docker compose up -d --build
```

- Dashboard: http://localhost:5173 · API: http://localhost:4000/api/health
- Tecnologias: Node.js/TypeScript, React + Vite + TailwindCSS + Recharts, Socket.io
- Alertas: Telegram (Bot API) e/ou E-mail (SMTP), com cooldown por device+métrica

> Documentação completa, variáveis de ambiente e API: [platform/README.md](platform/README.md).

---

### ⚠️ Segurança

Antes de compartilhar o repositório, remova TODAS as credenciais reais:

```bash
# Regenera template sem dados sensíveis
cp firmware/gateway/configNode.h firmware/gateway/configNode.h.template

# Verifique o que vai no commit
git diff --cached

# Faça o commit
git add -A
git commit -m "descrição segura"
```

> Evite commitar `configNode.h` com Wi-Fi SSID/senha, `nvs_secrets.h` com DevEUI/AppKey reais, e o `.ino` com credenciais hardcoded.

## Estrutura

```
LoraWan-project/
├── platform/                                 # SaaS multi-tenant (backend + frontend)
│   ├── docker-compose.yml                    # backend + postgres (TimescaleDB) + frontend (nginx)
│   ├── .env.example                          # todas as variáveis de ambiente
│   ├── backend/                              # Node.js/TypeScript (MQTT, REST, Socket.io, alertas)
│   │   └── src/
│   │       ├── index.ts                      # orquestração (HTTP + Socket.io + MQTT)
│   │       ├── mqtt/                         # cliente MQTT + parser v4
│   │       ├── db/                           # pool, migrate e init.sql (TimescaleDB)
│   │       ├── services/                     # persistência em batch, live, threshold engine
│   │       ├── alerts/                       # Telegram + E-mail
│   │       └── routes/                       # API REST
│   └── frontend/                             # React (Vite + Tailwind + Recharts)
│       └── src/
│           ├── api/                          # cliente REST
│           ├── socket/                       # Socket.io-client
│           └── components/                   # Cards, gráfico real-time, histórico, alertas
│
├── infrastructure/                           # Stack ChirpStack Docker (Network Server)
│   ├── docker-compose.yml                    # ChirpStack, gateway-bridge, REST API, DB, broker
│   ├── Makefile                              # importação de perfis de dispositivo
│   ├── app/                                  # webapp Flask de monitoramento
│   └── configuration/                        # chirpstack, gateway-bridge, mosquitto, postgresql
│
├── firmware/
│   ├── end-device/                           # Firmware do nó sensor (ESP32 + RFM95 + LDR)
│   │   ├── end-device.ino                    # Sketch principal
│   │   ├── config.h                          # Constantes (NVS, TX interval)
│   │   ├── lmic_project_config.h             # Configuração LMIC (SX1276, AU915)
│   │   ├── 1_PHY.ino ... 5_APP.ino           # Camadas PHY/MAC/NET/TRANSP/APP
│   └── gateway/                              # Firmware do gateway single-channel
│       ├── gateway.ino                       # Sketch principal
│       ├── configGway.h                      # Configuração de banda e recursos
│       ├── configNode.h                      # Credenciais WiFi e lista de nós
│       ├── loraModem.h                       # Definições do rádio e pinagens
│       └── _*.ino                            # Módulos (WiFi, Semtech UDP, web, OTA, ...)
│
├── docs/                                     # Manuais, análise de segurança, specs/plans
├── PRD_PLATAFORMA_IOT.md                     # Requisitos do produto (Fase A)
└── README.md
```
