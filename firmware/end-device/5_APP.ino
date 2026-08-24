//=======================================================================
//  CAMADA DE APLICAÇÃO — 5_APP.ino
//
//  Responsabilidades:
//    - Leitura do sensor LDR (ADC 12-bits, média de 8 amostras)
//    - Montagem do payload MoT LoRaWAN de uplink (36 bytes)
//

// -----------------------------------------------------------------
//  Porta de aplicação LoRaWAN (FPort — definida em config.h)
// -----------------------------------------------------------------
#include "config.h"

void APP_radio_send_UL(){

    // Lê o valor do sensor LDR
    uint16_t ldrValue = readLDR();

    float    voltage  = (ldrValue / 4095.0f) * 3.3f;
    Serial.printf("[SENSOR] LDR raw: %u  |  Voltage: %.3fV  |  FCnt: %u\n",
                  ldrValue, voltage, LMIC.seqnoUp);
    
    // Lê o nível de Bateria do Módulo Nó Sensor
    uint16_t bateria = analogRead(BAT_PIN); // PIN D32
    float    voltage_bat  = (bateria * 3.3f ) / 4095.0f;
    uint16_t voltBatInt = (uint16_t)(voltage_bat * 100);
    Serial.print(F("voltBatInt="));
    Serial.println(voltBatInt);

    // Lê o estado do botão do End Device
    uint8_t botao = 0;
    uint8_t estadoBotao = digitalRead(BOTAO_PIN);
    if (estadoBotao == HIGH) {
        // Botão pressionado
        botao = 1;
    }
    else{
        botao = 0;
    }


    // BYTES CAMADA DE APLICAÇÂO    
    // LDR - Luminosidade
    Pacote_UL[16] = TIPO_SENSOR_LDR;
    Pacote_UL[17] = (ldrValue >> 8) & 0xFF;
    Pacote_UL[18] =  ldrValue       & 0xFF;


    // Tensão da Bateria
    Pacote_UL[19] = TIPO_SENSOR_BAT;
    Pacote_UL[20] = (voltBatInt >> 8) & 0xFF;
    Pacote_UL[21] =  voltBatInt       & 0xFF;

    // Estado do Botão do End Device
    Pacote_UL[22] = botao;

    // Latitude
    int32_t lat =  LATITUDE;
    Pacote_UL[23] = TIPO_SENSOR_GPS;
    Pacote_UL[24]  = (lat >> 24) & 0xFF;
    Pacote_UL[25]  = (lat >> 16) & 0xFF;
    Pacote_UL[26] = (lat >> 8)  & 0xFF;
    Pacote_UL[27] =  lat        & 0xFF;

    // Longitude
    int32_t lon = LONGITUDE;
    Pacote_UL[28] = (lon >> 24) & 0xFF;
    Pacote_UL[29] = (lon >> 16) & 0xFF;
    Pacote_UL[30] = (lon >> 8)  & 0xFF;
    Pacote_UL[31] =  lon        & 0xFF;

    // Altitude (em metros)
    int32_t alt = ALTITUDE;
    Pacote_UL[32] = (alt >> 24) & 0xFF;
    Pacote_UL[33] = (alt >> 16) & 0xFF;
    Pacote_UL[34] = (alt >> 8)  & 0xFF;
    Pacote_UL[35] =  alt        & 0xFF;    
}

// -----------------------------------------------------------------
//  LÊ SENSOR — LDR (ADC 12-bits, Média de 8 amostras)
// -----------------------------------------------------------------
uint16_t readLDR() {
    uint32_t soma = 0;
    for (int i = 0; i < NUM_LEITURA_LDR; i++) {
        soma += analogRead(LDR_PIN);
        delay(2);
    }
    return (uint16_t)(soma / NUM_LEITURA_LDR);
}

