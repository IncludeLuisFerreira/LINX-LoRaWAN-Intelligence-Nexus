/*
//  Framework TpM aplicado a um End Device LoRaWAN Classe A - com Pacote MoT
//  TpM (Three-Phase Methodology - Wisstek - Laboratório de Soluções IoT - UNICAMP)
//  MoT - Management Over Tunneling
//
//  End Device Tipo A - LoRaWAN — OTAA (Over-The-Air Activation)
//  Hardware: ESP32 Dev Kit 1 - Module 30 pinos + rádio LoRa RFM95
//  Frequência: 916.8 MHz (AU915 canal 8, fixo)
//  Modo: OTAA, Classe A (Somente Uplinks, sem Confirmação/Downlinks/RX)
//
//  Bibliotecas requeridas:
//    - MCCI LoRaWAN LMIC library (arduino-lmic by mcci-catena)
//
//  Chaves OTAA fornecidas pelo Servidor de Rede - Network Server (Chirpstack, etc.)
//  Fluxo: boot -> Join Request -> Join Accept (RX1) -> sessão derivada -> uplinks.
//  Firmware desenvolvido para Gateways Monocanal LoRaWAN
//
//  NVS Wear Leveling:
//    O frame counter é salvo em 100 slots rotativos no NVS.
//    A cada salvamento, usa-se o próximo slot no ciclo circular.
//    Na leitura, percorre todos os slots e retorna o maior valor.
//    Isso distribui as escritas e multiplica a vida útil da flash por ~100x.
//    Com flash típica de 10.000 ciclos/célula e FCNT_SAVE_EVERY=10:
//      - Sem wear leveling: ~100.000 uplinks por vida útil
//      - Com wear leveling: ~10.000.000 uplinks por vida útil
//
//  Nota OTAA: a cada nova sessão o FCnt reinicia em 0 no servidor.
//  Em EV_JOINED o contador NVS é zerado (nova sessão).
*/

// Bibliotecas requeridas
#include <Arduino.h>
#include <SPI.h>

// Define ANTES de incluir a LMIC — habilita LMIC_setClockError()
// Sem isso a função é compilada como no-op e não tem efeito
#define LMIC_ENABLE_arbitrary_clock_error 1

#include <lmic.h>
#include <hal/hal.h>
#include <Preferences.h>    // ESP32 NVS — Mantém o contador de Uplinks mesmo após reinicializações.
                            // Necessário para Servidor TTN não identificar o End device como impostor/ghost

// -----------------------------------------------------------------
//  Constantes NVS (definidas em config.h)
// -----------------------------------------------------------------
#include "config.h"

// -----------------------------------------------------------------
//  MAPEAMENTO PINAGEM - RFM95 - ESP32 Dev Module Kit Vs.1
// -----------------------------------------------------------------
#define SCK_PIN   5
#define MISO_PIN  19
#define MOSI_PIN  27
#define RST_PIN   14
#define NSS_PIN   18
#define DIO0_PIN  26
#define DIO1_PIN  35
#define DIO2_PIN  34

// Sensor LDR
#define LDR_PIN   36   // ADC1_CH0 — sensor LDR

// Medido da Bateria
#define BAT_PIN   32  // ADC1_CH4 - Bateria End Device (APP)  - NÃO IMPLEMENTADO NO HARDWARE PKLORA

// Pinos de Entrada Digitais
#define BOTAO_PIN   39   // Pino do Botão - PIN VN

// Pinos de Saída Digitais
#define LED_VERMELHO_PIN  4
#define LED_AMARELO_PIN  2
#define LED_VERDE_PIN  15

// --- 3. Variáveis Globais e de Configuração ---
const int MY_ID = 3; // Identificação (ID de rede) deste Nó Sensor
const int GATEWAY_ID = 0; // Identificação (ID de rede) do Destino Gateway deste Pacote

// Tipos dos Sensores
const int TIPO_SENSOR_LDR = 44; //SENSOR LDR
const int TIPO_SENSOR_BAT = 11; // SENSOR BATERIA - NÃO IMPLEMENTADO NO HARDWARE PKLORA
const int TIPO_SENSOR_GPS = 10; // TIPO DO SENSOR GPS - VIA SOFTWARE

// Posição GPS do End Device PKLoRa
// -22.820984, -47.066727
#define LATITUDE  -22.820984                           	    // Latitude
#define LONGITUDE -47.066727                                // Longitude
#define ALTITUDE  625		                   			    // Altitude

// -----------------------------------------------------------------
//  CREDENCIAIS LoRaWAN - tipo OTAA
//  Geradas na migração ABP -> OTAA e armazenadas em nvs_secrets.h
//  (arquivo NÃO versionado). Devem ser cadastradas no ChirpStack:
//    DevEUI  = 07E32A82697444B9
//    AppEUI  = 0000000000000000
//    AppKey  = 1FD648EA9F3A1E2D014D8FF82C35683C
//
//  O LMIC chama os_getDevEui/os_getArtEui/os_getDevKey (config.h) que
//  leem essas chaves. Aqui NÃO há DevAddr/NwkSKey/AppSKey fixos —
//  a sessão é derivada do Join Accept recebido do servidor.
// -----------------------------------------------------------------

// -----------------------------------------------------------------
//  LMIC - Mapeamento da pinagem para Biblioteca LMIC
// -----------------------------------------------------------------
const lmic_pinmap lmic_pins = {
    .nss  = NSS_PIN,
    .rxtx = LMIC_UNUSED_PIN,
    .rst  = RST_PIN,
    .dio  = { DIO0_PIN, DIO1_PIN, DIO2_PIN },
};

// -----------------------------------------------------------------
//  SETUP
// -----------------------------------------------------------------
void setup() {

    Serial.begin(115200);
    delay(200);

    // Imprime no Serial Monitor a alocação de memória do contador de Uplinks
    while (!Serial && millis() < 3000);
    Serial.println(F("\nEnd Device LoRaWAN OTAA — Wear Leveling NVS"));
    Serial.printf("    Slots NVS: %u  |  Salva a cada: %u uplinks\n",
                  NVS_SLOT_COUNT, FCNT_SAVE_EVERY);
    Serial.printf("    Vida útil estimada: ~%lu uplinks\n\n",
                  (unsigned long)NVS_SLOT_COUNT * 10000UL * FCNT_SAVE_EVERY);
   
    // Inicializa o Botao como Entrada Digital do ESP32
    pinMode(BOTAO_PIN, INPUT); 

    // Inicializa os LEDs como Saídas Digitais do ESP32
    pinMode(LED_VERMELHO_PIN, OUTPUT);
    pinMode(LED_AMARELO_PIN, OUTPUT);
    pinMode(LED_VERDE_PIN, OUTPUT);    
       
    //  --- Atua Led vermelho  --- 
    digitalWrite(LED_VERMELHO_PIN, HIGH); // LIGA LED VERMELHO - INDIFERENTE PARA O BOOT

    //  --- Atua Led amarelo  --- 
    digitalWrite(LED_AMARELO_PIN, HIGH); // LIGA O LED AMARELO - DEVE SER HIGH DURANTE BOOT

    //  --- Atua Led verde  --- 
    digitalWrite(LED_VERDE_PIN, LOW);  // DESLIGA O LED VERDE - DEVE SER LOW DURANTE BOOT

    // Pinagem SPI para RFM95
    SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, NSS_PIN);
    delay(200);

    // Configuração ADC para o LDR
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    pinMode(LDR_PIN, INPUT);

    // Carrega frame counter persistente (wear leveling)
    // Necessário para a TTN evitar descarte do Uplink para não duplicidade entre Pacotes
    loadFrameCounter();

    // Inicializa Biblioteca LMIC
    os_init();
    LMIC_reset();

    // Aplica configuração de canal único em 916.8 MHz
    configura_camada_fisica();

    configura_camada_rede();

    // Compensa o erro de clock do oscilador do ESP32 nas janelas RX1/RX2
    // do Join Accept — necessário em OTAA para não perder o downlink.
    LMIC_setClockError(MAX_CLOCK_ERROR * 1 / 100);

    // OTAA: dispara o Join Request.
    // NÃO chamamos LMIC_setSession — a sessão é derivada do Join Accept.
    // O primeiro uplink só ocorre após EV_JOINED (ver onEvent em 2_MAC.ino).
    LMIC_startJoining();

    configura_camada_transporte();

    delay(200);
    //  --- Atua Led vermelho  --- 
    digitalWrite(LED_VERMELHO_PIN, LOW); // DESLIGA LED VERMELHO

    //  --- Atua Led amarelo  --- 
    digitalWrite(LED_AMARELO_PIN, LOW); // DESLIGA O LED AMARELO

    //  --- Atua Led verde  --- 
    digitalWrite(LED_VERDE_PIN, LOW);  // DESLIGA O LED VERDE

    Serial.println(F("[OTAA] Aguardando Join Accept...\n"));

    // NÃO agenda uplink aqui — aguarda EV_JOINED.
}

// -----------------------------------------------------------------
//  LOOP principal — Delega ao Scheduler da Biblioteca LMIC
// -----------------------------------------------------------------
void loop() {
    
    os_runloop_once();
}
