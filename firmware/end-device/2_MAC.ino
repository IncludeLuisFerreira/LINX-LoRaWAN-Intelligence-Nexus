//=======================================================================
//  CAMADA MAC — 2_MAC.ino
//
//  Responsabilidades:
//    - Gerenciamento da sessão OTAA no LMIC (join, eventos, retries)
//    - Callback de eventos LMIC (onEvent)
//    - Gerenciamento do frame counter (FCntUp) com wear leveling no NVS
//
//  Wear Leveling:
//    O FCntUp é salvo em NVS_SLOT_COUNT slots rotativos.
//    A cada salvamento, usa o próximo slot circular.
//    Na leitura, percorre todos os slots e retorna o maior valor.
//    Isso distribui as escritas, multiplicando a vida útil da flash
//    por ~NVS_SLOT_COUNT vezes.
//
//    Layout NVS (namespace "lorawan"):
//      "fcnt_00" … "fcnt_99"  → valores do frame counter (uint32)
//      "fcnt_idx"             → índice do último slot gravado (uint8)
//
//  OTAA: em cada nova sessão o FCnt reinicia em 0. Em EV_JOINED o
//  contador persistido é zerado.
//=======================================================================

// -----------------------------------------------------------------
//  Constantes NVS (definidas em config.h)
// -----------------------------------------------------------------
#include "config.h"

void MAC_send_UL(){

    // BYTES CAMADA MAC
    Pacote_UL[4] = (fcntUp/256);   // Inteiro - Frame Counter Uplink
    Pacote_UL[5] = (fcntUp%256);   // Resto - Frame Counter Uplink
    Pacote_UL[6] = 0;   // 
    Pacote_UL[7] = 0;   // 

}

// -----------------------------------------------------------------
//  LMIC - CALLBACK DE EVENTOS
// -----------------------------------------------------------------

// Controle de retries OTAA
static uint8_t otaaAttempts = 0;

void OTAA_retry_join(osjob_t* j) {
    if (otaaAttempts >= OTAA_MAX_ATTEMPTS) {
        Serial.printf("[OTAA] Falha definitiva após %u ciclos — aguardando reset do nó\n",
                      OTAA_MAX_ATTEMPTS);
        return;
    }

    Serial.printf("[OTAA] Retentativa %u/%u...\n", otaaAttempts + 1, OTAA_MAX_ATTEMPTS);
    LMIC_reset();
    configura_camada_fisica();
    LMIC_startJoining();
}

void onEvent(ev_t ev) {
    switch (ev) {
        case EV_JOINED:
            Serial.println(F("[LMIC] EV_JOINED"));
            otaaAttempts = 0;

            // Nova sessão OTAA: FCnt reinicia em 0 (servidor espera isso)
            fcntUp = 0;
            fcntSinceSave = 0;
            resetFrameCounterNVS();

            // O LMIC pode ter alterado canais/DR no processo de join.
            // Reaplica canal único 916.8 MHz / SF7 e desativa ADR/LinkCheck.
            configura_camada_fisica();
            LMIC_setLinkCheckMode(0);

            // Inicia o primeiro ciclo de uplinks
            os_setCallback(&Envia_pkt_UL, PHY_Envia_UL);
            break;

        case EV_JOIN_FAILED:
            Serial.println(F("[LMIC] EV_JOIN_FAILED"));
            // LMIC esgotou as tentativas internas (default ~8). Agenda retry.
            otaaAttempts++;
            os_setTimedCallback(&Envia_pkt_UL,
                os_getTime() + ms2osticks(OTAA_RETRY_DELAY_MS), OTAA_retry_join);
            break;

        case EV_REJOIN_FAILED:
            Serial.println(F("[LMIC] EV_REJOIN_FAILED"));
            otaaAttempts++;
            os_setTimedCallback(&Envia_pkt_UL,
                os_getTime() + ms2osticks(OTAA_RETRY_DELAY_MS), OTAA_retry_join);
            break;

        case EV_TXCOMPLETE:
            Serial.println(F("[LMIC] EV_TXCOMPLETE"));

            // Atualiza fcntUp com o valor atual do LMIC
            fcntUp = LMIC.seqnoUp;
            fcntSinceSave++;

            // Persiste a cada FCNT_SAVE_EVERY uplinks
            // Salva com margem (+FCNT_SAVE_EVERY) para cobrir possível crash
            // antes do próximo ciclo de salvamento
            if (fcntSinceSave >= FCNT_SAVE_EVERY) {
                saveFrameCounter(fcntUp + FCNT_SAVE_EVERY);
                fcntSinceSave = 0;
            }

            if (LMIC.txrxFlags & TXRX_ACK)
                Serial.println(F("  ACK recebido"));
            if (LMIC.dataLen)
                Serial.printf("  Downlink %d byte(s) na porta %d\n",
                              LMIC.dataLen, LMIC.frame[LMIC.dataBeg - 1]);

            // Agenda próximo uplink
            os_setTimedCallback(&Envia_pkt_UL,
                os_getTime() + ms2osticks(TX_INTERVAL_MS), PHY_Envia_UL);
            break;

        case EV_TXSTART:
            Serial.println(F("[LMIC] EV_TXSTART"));
            Serial.print("Freq: ");
            Serial.print(LMIC.freq);
            Serial.print("\n");
            break;

        case EV_RXSTART:
            // Dispara frequentemente — suprimido para manter serial limpo
            break;

        case EV_RESET:
            Serial.println(F("[LMIC] EV_RESET"));
            break;

        case EV_LINK_DEAD:
            Serial.println(F("[LMIC] EV_LINK_DEAD — verifique FCnt no servidor"));
            break;

        default:
            Serial.printf("[LMIC] Evento: %u\n", (unsigned)ev);
            break;
    }
}

