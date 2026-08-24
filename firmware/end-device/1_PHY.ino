//=======================================================================
//  CAMADA FÍSICA — 1_PHY.ino
//
//  Responsabilidades:
//    - Mapeamento dos pinos do RFM95 para a biblioteca LMIC
//    - Inicialização do LMIC (os_init / LMIC_reset)
//    - Configuração do canal único (916.8 MHz — AU915 canal 8)
//    - Parâmetros de rádio: SF, potência, ADR, link check
//    - OTAA: proteção de uplink (só com sessão ativa) e retry de join
//=======================================================================


// -----------------------------------------------------------------
//  CONFIGURAÇÃO DO CANAL — 916.8 MHz somente
//  AU915 canal 8 conforme Gateway Monocanal
// -----------------------------------------------------------------
void configura_camada_fisica() {
    // 1. Desativa todos os 72 canais padrão da especificação
    for (int i = 0; i < 72; i++) {
        LMIC_disableChannel(i);
    }

    // 2. Habilita APENAS o canal 8 
    // No padrão AU915, o Canal 8 corresponde exatamente a 916.8 MHz
    LMIC_enableChannel(8);

    // 3. Define o Data Rate (SF7, BW125) e a potência de transmissão (14 dBm)
    LMIC_setDrTxpow(DR_SF7, 14);

    // 4. Desativa o ADR (Adaptive Data Rate) para impedir que a rede mude o SF
    LMIC_setAdrMode(0);

    // 5. Desativa o LinkCheckMode
    LMIC_setLinkCheckMode(0);
}

// -----------------------------------------------------------------
//  Monta o PAYLOAD e Envia
// -----------------------------------------------------------------
void PHY_Envia_UL(osjob_t* j) {

    // OTAA: só transmite dados após o join (sessão ativa)
    if (LMIC.opmode & OP_JOINING) {
        Serial.println(F("[TX] Ainda em JOINING — pulando uplink"));
        return;
    }
    if (LMIC.devaddr == 0) {
        Serial.println(F("[TX] Sem sessão ativa — pulando uplink"));
        return;
    }

    // Ignora Operação RX - Downlink
    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("[TX] Pendente — pulando este ciclo"));
        return;
    }

    // Liga o LED Vermelho indicando envio do Pacote de Uplink
    digitalWrite(LED_VERMELHO_PIN, HIGH);

   

    // BYTES CAMADA APLICAÇÃO
    APP_radio_send_UL();

    // BYTES CAMADA TRANSPORTE
    Transp_radio_send_UL();

    // BYTES CAMADA DE REDE - NET
    NET_radio_send_UL();    

    // BYTES CAMADA DE REDE - NET
    MAC_send_UL();

    // BYTES CAMADA PHY
    Pacote_UL[0] = 0;     // RSSId; // RSSId RX Rádio LoRa
    Pacote_UL[1] = 0;     // SNRd; // SNRu RX Rádio LoRa
    Pacote_UL[2] = 0;     // RSSIu TX Rádio LoRa - Será mensurado pelo Transceptor LoRa Gateway
    Pacote_UL[3] = 0;     // SNRu TX Rádio LoRa - Será mensurado pelo Transceptor LoRa Gateway

    // Uplink não confirmado na porta 1
    LMIC_setTxData2(1, Pacote_UL, sizeof(Pacote_UL), 0);

    Serial.println(F("[TX] Pacote Enviado"));

    digitalWrite(LED_VERMELHO_PIN, LOW); // Turn the LED OFF

}

