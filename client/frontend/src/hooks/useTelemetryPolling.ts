import { useEffect, useRef } from 'react';
import { telemetryService, type TelemetryItem } from '../services/telemetry';

export const DEFAULT_POLL_INTERVAL_MS = 5000;

/**
 * Itens buscados por tick de polling. Maior que 1 para não perder eventos que
 * chegam em rajada entre dois ticks; o dedupe por `(dev_eui, time, event_type)`
 * de `appendItem` descarta os já vistos.
 */
export const POLL_LIMIT = 50;

/**
 * Fallback de polling REST quando o WebSocket de telemetria está offline.
 * Busca os itens mais recentes em `GET /telemetry?dev_eui=<eui>&limit=<POLL_LIMIT>`
 * a cada `intervalMs` e entrega cada um via `onItem`; o dedupe do consumidor
 * descarta repetições. Erros de rede são ignorados para não interromper o timer.
 * Sem reconexão de WebSocket aqui (issue #100).
 */
export function useTelemetryPolling(
  devEui: string,
  enabled: boolean,
  onItem: (item: TelemetryItem) => void,
  intervalMs: number = DEFAULT_POLL_INTERVAL_MS,
): void {
  const onItemRef = useRef(onItem);

  useEffect(() => {
    onItemRef.current = onItem;
  }, [onItem]);

  useEffect(() => {
    if (!enabled || !devEui) return;

    const poll = async () => {
      try {
        const history = await telemetryService.history(devEui, {
          limit: POLL_LIMIT,
        });
        for (const item of history.items) onItemRef.current(item);
      } catch {
        /* rede indisponível: mantém o timer e tenta no próximo tick */
      }
    };

    const id = setInterval(poll, intervalMs);
    return () => clearInterval(id);
  }, [devEui, enabled, intervalMs]);
}
