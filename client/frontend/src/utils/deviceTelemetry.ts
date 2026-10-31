import type { TelemetryItem } from '../services/telemetry';

export const DEVICE_ONLINE_WINDOW_MS = 60_000;

const numberFormatter = new Intl.NumberFormat('pt-BR', {
  maximumFractionDigits: 3,
});

function formatScalar(value: unknown): string {
  return typeof value === 'number'
    ? numberFormatter.format(value)
    : String(value);
}

export function latestTelemetry(items: TelemetryItem[]): TelemetryItem | null {
  let latest: TelemetryItem | null = null;
  let latestMs = Number.NEGATIVE_INFINITY;

  for (const item of items) {
    const ms = Date.parse(item.time);
    if (Number.isNaN(ms) || ms <= latestMs) continue;
    latest = item;
    latestMs = ms;
  }

  return latest;
}

export function isDeviceOnline(
  last: TelemetryItem | null,
  now: number = Date.now(),
): boolean {
  if (!last) return false;
  const time = Date.parse(last.time);
  if (Number.isNaN(time)) return false;
  const age = now - time;
  // Timestamp futuro é offline: evita falso online por skew de relógio.
  return age >= 0 && age < DEVICE_ONLINE_WINDOW_MS;
}

export function formatTelemetryValue(payload: Record<string, unknown>): string {
  if (
    typeof payload !== 'object' ||
    payload === null ||
    Array.isArray(payload)
  ) {
    return '—';
  }

  const parts: string[] = [];
  for (const [key, value] of Object.entries(payload)) {
    if (
      typeof value === 'string' ||
      typeof value === 'number' ||
      typeof value === 'boolean'
    ) {
      parts.push(`${key}: ${formatScalar(value)}`);
    }
  }
  return parts.length > 0 ? parts.join(' · ') : '—';
}
