import { useEffect, useRef } from 'react';
import { telemetryService, type TelemetryItem } from '../services/telemetry';

export const DEFAULT_POLL_INTERVAL_MS = 5000;

/** Item de maior `time` na lista, ou `null` quando vazia ou sem data válida. */
function latestByTime(items: TelemetryItem[]): TelemetryItem | null {
  let latest: TelemetryItem | null = null;
  let latestMs = Number.NEGATIVE_INFINITY;
  for (const item of items) {
    const ms = Date.parse(item.time);
    if (!Number.isNaN(ms) && ms > latestMs) {
      latestMs = ms;
      latest = item;
    }
  }
  return latest;
}

/**
 * Fallback de polling REST quando o WebSocket de telemetria está offline.
 * Busca o item mais recente em `GET /telemetry?dev_eui=<eui>&limit=1` a cada
 * `intervalMs` e o entrega via `onItem`. Erros de rede são ignorados para não
 * interromper o timer. Sem reconexão de WebSocket aqui (issue #100).
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
        const history = await telemetryService.history(devEui, { limit: 1 });
        const latest = latestByTime(history.items);
        if (latest) onItemRef.current(latest);
      } catch {
        /* rede indisponível: mantém o timer e tenta no próximo tick */
      }
    };

    const id = setInterval(poll, intervalMs);
    return () => clearInterval(id);
  }, [devEui, enabled, intervalMs]);
}
