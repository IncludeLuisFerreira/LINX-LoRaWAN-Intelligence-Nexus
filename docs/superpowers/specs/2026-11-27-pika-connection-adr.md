# ADR — Pika 1.5.0 com `pika.Connection`

**Status:** aceito (spike #302)
**Data:** 2026-11-27

## Contexto

A Fatia 4 depende de validar a API `pika.Connection` do Pika 1.5.0 antes de
migrar publisher/consumer. O `pika.BlockingConnection` está deprecado e sai no
Pika 2.0.

## Spike executado

Ambiente: Pika 1.5.0, Python 3.14, RabbitMQ 3-management efêmero.

Resultados:

- **Publisher confirmado:** `confirm_delivery(ack_nack_callback)` +
  `basic_publish(..., on_publish=cb)` entrega o delivery tag; ACK do broker é
  observável e mapeável para o publish.
- **Não roteável:** `mandatory=True` + `add_on_return_callback` entrega o
  retorno e, em seguida, o ACK do broker. O publisher precisa registrar o
  retorno (por header/message id) para não tratar como sucesso.
- **Consumo:** `basic_consume(auto_ack=False)` com ACK manual funciona; o
  callback roda na thread de trabalho do canal.
- **NACK → DLX:** `basic_nack(requeue=False)` em fila com DLX levou a mensagem
  à DLQ.
- **Broker cai:** `on_close_callback` disparou com `CONNECTION_FORCED
  (shutdown)`. A reconexão **não é automática**: a primeira tentativa logo após
  o restart falhou com `IncompatibleProtocolError`; é obrigatório retry com
  backoff.
- **Shutdown:** `connection.close(timeout=...)` encerra a thread `pika-ioloop`;
  nenhuma thread residual.

## Decisão

Usar `pika.Connection` como única API de produção. `pika.BlockingConnection`
não deve aparecer no código de produção.

Consequências:

1. O publisher do adaptador precisa reconstruir a semântica de exceção
   (`UnroutableError`/`NackError`) a partir de callbacks e futures.
2. O connection manager precisa reconectar com backoff e recriar canais,
   topologia e consumidores após `on_close`.
3. O consumidor bloqueia a thread principal em `stop_event.wait`, não em
   `process_data_events`.
4. Testes que simulavam `BlockingConnection` migram para fakes do adaptador.

## Alternativas rejeitadas

- Manter `BlockingConnection` até o Pika 2.0: adia a migração inevitável.
- Migrar para `rabbitpy`: contraria a decisão A+C do design.
