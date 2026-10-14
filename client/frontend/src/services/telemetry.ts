import { api } from './api';

export interface TelemetryItem {
  time: string;
  dev_eui: string;
  payload: Record<string, unknown>;
  rssi: number | null;
  snr: number | null;
  app_id: string | null;
  event_type: string;
}

export interface TelemetryHistory {
  items: TelemetryItem[];
  next_cursor: string | null;
}

export interface TelemetryPoint {
  time: string;
  value: number;
}

export interface HistoryQuery {
  limit?: number;
  before?: string;
}

export const DEFAULT_TELEMETRY_LIMIT = 100;

export const telemetryService = {
  history: async (
    devEui: string,
    query: HistoryQuery = {},
  ): Promise<TelemetryHistory> => {
    const response = await api.get<TelemetryHistory>('/telemetry', {
      params: {
        dev_eui: devEui,
        limit: query.limit ?? DEFAULT_TELEMETRY_LIMIT,
        before: query.before,
      },
    });
    return response.data;
  },
};

/** Chaves numéricas presentes no payload dos itens, na ordem de aparição. */
export function numericMetrics(items: TelemetryItem[]): string[] {
  const keys = new Set<string>();
  for (const item of items) {
    for (const [key, value] of Object.entries(item.payload ?? {})) {
      if (typeof value === 'number' && Number.isFinite(value)) keys.add(key);
    }
  }
  return [...keys];
}

/** Converte itens de telemetria em série `{ time, value }` ordenada por tempo. */
export function buildSeries(
  items: TelemetryItem[],
  metric: string,
): TelemetryPoint[] {
  return items
    .map((item) => ({ time: item.time, value: item.payload?.[metric] }))
    .filter(
      (point): point is TelemetryPoint =>
        typeof point.value === 'number' && Number.isFinite(point.value),
    )
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
}

/** URL absoluta do WebSocket de telemetria para o app. */
export function buildTelemetrySocketUrl(appId: string): string {
  const base = import.meta.env.VITE_WS_URL;
  const prefix =
    base && base.trim() !== ''
      ? base.replace(/\/$/, '')
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
  return `${prefix}/ws/telemetry/${appId}`;
}

/** Valida e normaliza uma mensagem recebida do WebSocket. */
export function parseTelemetryMessage(raw: unknown): TelemetryItem | null {
  let data: unknown = raw;
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (typeof data !== 'object' || data === null) return null;
  const record = data as Record<string, unknown>;
  const { time, dev_eui, payload } = record;
  if (typeof time !== 'string' || typeof dev_eui !== 'string') return null;
  if (typeof payload !== 'object' || payload === null) return null;
  return {
    time,
    dev_eui,
    payload: payload as Record<string, unknown>,
    rssi: typeof record.rssi === 'number' ? record.rssi : null,
    snr: typeof record.snr === 'number' ? record.snr : null,
    app_id: typeof record.app_id === 'string' ? record.app_id : '',
    event_type: typeof record.event_type === 'string' ? record.event_type : '',
  };
}

/** Anexa um item deduplicando por (dev_eui, time, event_type), ordenado por time. */
export function appendItem(
  items: TelemetryItem[],
  item: TelemetryItem,
): TelemetryItem[] {
  const exists = items.some(
    (current) =>
      current.dev_eui === item.dev_eui &&
      current.time === item.time &&
      current.event_type === item.event_type,
  );
  if (exists) return items;
  return [...items, item].sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
  );
}

export interface SeriesInput {
  key: string;
  label: string;
  data: TelemetryPoint[];
}

/**
 * Mescla várias séries em linhas indexadas por `time`, com uma chave por série.
 * Pontos de séries diferentes no mesmo instante ocupam a mesma linha.
 */
export function mergeSeries(
  series: SeriesInput[],
): Record<string, number | string>[] {
  const rows = new Map<string, Record<string, number | string>>();
  for (const entry of series) {
    for (const point of entry.data) {
      const row = rows.get(point.time) ?? { time: point.time };
      row[entry.key] = point.value;
      rows.set(point.time, row);
    }
  }
  return [...rows.values()].sort(
    (a, b) =>
      new Date(String(a.time)).getTime() - new Date(String(b.time)).getTime(),
  );
}
