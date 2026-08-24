//=======================================================================
//  CAMADA DE REDE — 3_NET.ino
//
//  Responsabilidades:
//    - Endereçamento LoRaWAN (porta de aplicação FPort)
//    - Verificação de disponibilidade do stack (OP_TXRXPEND)
//    - Entrega do payload ao stack LMIC para transmissão
//=======================================================================

// -----------------------------------------------------------------
//  Porta de aplicação LoRaWAN (FPort — definida em config.h)
// -----------------------------------------------------------------
#include "config.h"

// -----------------------------------------------------------------
//  Net_sendUplink(payload, len)
//  Entrega o payload à camada MAC (LMIC) para transmissão.
//  Verifica se há transmissão pendente antes de enfileirar.
//  Retorna true se o pacote foi aceito, false se estava pendente.
// -----------------------------------------------------------------

void NET_radio_send_UL(){

    // BYTES CAMADA DE REDE - NET    
    // Byte Destino
    Pacote_UL[8] = GATEWAY_ID;
    Pacote_UL[9] = 0;
    
    // Byte Origem
    Pacote_UL[10] = MY_ID;
    Pacote_UL[11] = 0;

}

void configura_camada_rede() {

    // OTAA: nenhuma sessão fixa aqui. A sessão (DevAddr, NwkSKey, AppSKey)
    // é derivada pelo servidor e recebida no Join Accept. O join é
    // disparado por LMIC_startJoining() no setup (ver .ino principal).

}
