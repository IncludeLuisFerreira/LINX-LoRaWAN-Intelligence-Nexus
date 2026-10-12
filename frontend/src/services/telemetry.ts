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
