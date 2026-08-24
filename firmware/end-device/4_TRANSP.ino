//=======================================================================
//  CAMADA DE TRANSPORTE — 4_TRANSP.ino
//
//  Responsabilidades:
//    - Contagem de uplinks transmitidos na sessão atual
//    - Controle do intervalo entre uplinks (agendamento via LMIC)
//    - Agendamento do próximo ciclo de transmissão
//=======================================================================


// -----------------------------------------------------------------
//  Porta de aplicação LoRaWAN (FPort — definida em config.h)
// -----------------------------------------------------------------
#include "config.h"


// -----------------------------------------------------------------
//  CONTADOR DE UPLINKS PERSISTENTE — NVS com Wear Leveling
//
//  Estratégia: NVS_SLOT_COUNT slots rotativos no NVS.
//  A cada salvamento, usa o próximo slot circular.
//  Na leitura, percorre todos os slots e retorna o maior valor.
//  Isso distribui as escritas e multiplica a vida útil da flash
//  por NVS_SLOT_COUNT vezes.
//
//  Layout NVS (namespace "lorawan"):
//    "fcnt_00" … "fcnt_99"  → valores do frame counter (uint32)
//    "fcnt_idx"             → índice do último slot gravado (uint8)
//
//  End Device ABP DEVE salvar o frame counter persistentemente.
//  Se o contador for reiniciado abaixo do último valor visto pelo
//  servidor, o servidor irá descartar os pacotes silenciosamente
//  (proteção contra ataques de repetição).
// -----------------------------------------------------------------

void Transp_radio_send_UL(){

    // Incrementa Contador Pacote UL
    PKT_UL = PKT_UL + 1;

    // BYTES CAMADA TRANSPORTE

    Pacote_UL[12] = 0;
    Pacote_UL[13] = 0;
    
    // Contador Pacote UL
    Pacote_UL[14] = (PKT_UL >> 8) & 0xFF;    
    Pacote_UL[15] =  PKT_UL       & 0xFF;

}


void configura_camada_transporte() {

    // OTAA: nada de sessão fixa neste ponto. O FCnt é zerado em EV_JOINED
    // (resetFrameCounterNVS) e passa a ser persistido com wear leveling
    // conforme os uplinks acontecem (ver onEvent em 2_MAC.ino).

}


// Gera a chave NVS de um slot: "fcnt_00" … "fcnt_99"
static void slotKey(uint8_t idx, char* buf) {
    snprintf(buf, 12, "fcnt_%02u", (unsigned)(idx % NVS_SLOT_COUNT));
}

/*
 * loadFrameCounter()
 * Percorre todos os NVS_SLOT_COUNT slots e retorna o maior fcntUp
 * encontrado — valor mais recente mesmo após crash ou reset.
 * Também recupera fcntSlotIdx para retomar a rotação corretamente.
 */
void loadFrameCounter() {
    prefs.begin(NVS_NAMESPACE, false);

    uint32_t maxVal  = 0;
    uint8_t  maxSlot = 0;
    char     key[12];

    for (uint8_t i = 0; i < NVS_SLOT_COUNT; i++) {
        slotKey(i, key);
        uint32_t val = prefs.getUInt(key, 0);
        if (val > maxVal) {
            maxVal  = val;
            maxSlot = i;
        }
    }

    fcntUp = maxVal;

    // Tenta usar o índice persistido para desempate e continuidade
    uint8_t savedIdx = prefs.getUChar(NVS_IDX_KEY, (maxSlot + 1) % NVS_SLOT_COUNT);
    char    savedKey[12];
    slotKey(savedIdx, savedKey);

    // Usa savedIdx somente se o slot apontado contém o valor máximo
    if (prefs.getUInt(savedKey, 0) >= maxVal) {
        fcntSlotIdx = (savedIdx + 1) % NVS_SLOT_COUNT;
    } else {
        // Retoma a partir do slot seguinte ao que continha o máximo
        fcntSlotIdx = (maxSlot + 1) % NVS_SLOT_COUNT;
    }

    prefs.end();

    Serial.printf("[NVS] FCntUp restaurado: %u  |  Próximo slot: %u/%u\n",
                  fcntUp, fcntSlotIdx, NVS_SLOT_COUNT);
}

/*
 * saveFrameCounter(fcnt)
 * Grava fcnt no slot atual da rotação, persiste o índice e avança
 * para o próximo slot. Cada chamada usa uma célula de flash diferente.
 *
 * ATENÇÃO: chame sempre com (LMIC.seqnoUp + FCNT_SAVE_EVERY) para
 * criar uma margem de segurança em caso de crash antes do próximo save.
 */
void saveFrameCounter(uint32_t fcnt) {
    char key[12];
    slotKey(fcntSlotIdx, key);

    prefs.begin(NVS_NAMESPACE, false);
    prefs.putUInt(key,      fcnt);
    prefs.putUChar(NVS_IDX_KEY, fcntSlotIdx);
    prefs.end();

    Serial.printf("[NVS] FCnt %u → slot %u (%s)  |  Próximo: %u\n",
                  fcnt, fcntSlotIdx, key,
                  (fcntSlotIdx + 1) % NVS_SLOT_COUNT);

    fcntSlotIdx = (fcntSlotIdx + 1) % NVS_SLOT_COUNT;
}

/*
 * resetFrameCounterNVS()
 * Zera o frame counter persistido e reinicia a rotação de slots.
 * Usado em EV_JOINED: cada sessão OTAA reinicia o FCnt em 0.
 */
void resetFrameCounterNVS() {
    prefs.begin(NVS_NAMESPACE, false);

    for (uint8_t i = 0; i < NVS_SLOT_COUNT; i++) {
        char key[12];
        slotKey(i, key);
        prefs.remove(key);
    }
    prefs.remove(NVS_IDX_KEY);

    prefs.end();

    fcntUp        = 0;
    fcntSinceSave = 0;
    fcntSlotIdx   = 0;

    Serial.println(F("[NVS] FCnt zerado (nova sessão OTAA)"));
}
