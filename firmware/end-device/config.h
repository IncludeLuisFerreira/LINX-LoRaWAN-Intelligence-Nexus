#ifndef CONFIG_H
#define CONFIG_H

//=======================================================================
//  config.h — Constantes globais do projeto
//
//  Este arquivo é incluído pelos arquivos .ino que precisam das
//  constantes antes que o Arduino IDE finalize a concatenação.
//  Use: #include "config.h"
//=======================================================================

// Credenciais OTAA — arquivo NÃO versionado (ver .gitignore)
#include "nvs_secrets.h"

Preferences prefs;
#define NVS_NAMESPACE     "lorawan"
#define NVS_SLOT_COUNT    100          // Número de slots rotativos
#define NVS_IDX_KEY       "fcnt_idx"   // Chave do índice atual
#define FCNT_SAVE_EVERY   10           // Salva a cada N uplinks (reduz desgaste)

static uint32_t fcntUp        = 0;
static uint32_t fcntSinceSave = 0;
static uint8_t  fcntSlotIdx   = 0;    // Slot atual na rotação (0 … NVS_SLOT_COUNT-1)


// -----------------------------------------------------------------
//  INTERVALOS de tempo entre UPLINK
// -----------------------------------------------------------------
#define TX_INTERVAL_MS  15000UL   // 120 seconds // 2 minutos Padrão TTN Free

// -----------------------------------------------------------------
//  TAMANHO DO PAYLOAD (BYTES ÚTEIS)
#define TAMANHO_PACOTE 36   // MoT => 36 bytes
#define NUM_LEITURA_LDR 4 // Média de x Leituras LDR - evitar oscilações

// Monta o Pacote de Uplink => Payload
uint8_t Pacote_UL[TAMANHO_PACOTE];

// -----------------------------------------------------------------
//  OTAA keys — fornecidas pelos callbacks abaixo (ver nvs_secrets.h)
//  O LMIC chama estas funcoes quando monta o Join Request.
//  DEVEUI/APPEUI: LSB-first. APPKEY: ordem direta.
// -----------------------------------------------------------------
void os_getArtEui(u1_t* buf) { memcpy_P(buf, APPEUI, 8); }
void os_getDevEui(u1_t* buf) { memcpy_P(buf, DEVEUI, 8); }
void os_getDevKey(u1_t* buf) { memcpy_P(buf, APPKEY, 16); }

// -----------------------------------------------------------------
//  OTAA retry — tentativas de join com backoff
// -----------------------------------------------------------------
#define OTAA_MAX_ATTEMPTS   5   // ciclos de retry (cada ciclo = 8 joins do LMIC)
#define OTAA_RETRY_DELAY_MS 30000UL

// -----------------------------------------------------------------
//  GLOBAL
// -----------------------------------------------------------------
static osjob_t Envia_pkt_UL;

// Contador UL
uint16_t PKT_UL = 0;

// -----------------------------------------------------------------
//  Porta de aplicação LoRaWAN (FPort)
// -----------------------------------------------------------------
#define LORAWAN_FPORT   1

#endif // CONFIG_H


/*
bytes do  mot:

--- PHY ---
00 -> RSSId
01 -> SNRd
02 -> RSSIu
03 -> SNRu
04 -> SF
05 -> BW
06 -> CR
07 -> TX Power
--- MAC ---
08 -> Intervalo de medidas
--- NET ---
09 -> Origem (End-Device)
10 -> Destino (Gateway)
--- TRANSP ---
11 -> Cont-PCT_Down-link
12 -> Cont-PCT_Up-link
--- Grandeza ---
13 -> Inteiro (LDR)
14 -> Resto (LDR)
--- Reservados ---
15 -> TBD
16 -> TBD
17 -> TBD
18 -> TBD
19 -> TBD
20 -> TBD
21 -> TBD
22 -> TBD
23 -> TBD
24 -> TBD
24 -> TBD
25 -> TBD
26 -> TBD
27 -> TBD
28 -> TBD
29 -> TBD
30 -> TBD
31 -> TBD
32 -> TBD
33 -> TBD
34 -> TBD
35 -> TBD
36 -> TBD
37 -> TBD
38 -> TBD
39 -> TBD
40 -> TBD
41 -> TBD
42 -> TBD
43 -> TBD
44 -> TBD
45 -> TBD
46 -> TBD
47 -> TBD
48 -> TBD
49 -> TBD
50 -> TBD
*/
