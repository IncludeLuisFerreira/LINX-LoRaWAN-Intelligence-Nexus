import { describe, expect, it } from 'vitest';
import type { TelemetryItem } from '../services/telemetry';
import {
  DEVICE_ONLINE_WINDOW_MS,
  formatTelemetryValue,
  isDeviceOnline,
  latestTelemetry,
} from './deviceTelemetry';

const item = (
  time: string,
  payload: Record<string, unknown> = {},
): TelemetryItem => ({
  time,
  dev_eui: 'aabbccddeeff0011',
  payload,
  rssi: -70,
  snr: 7.5,
  app_id: 'app-1',
  event_type: 'up',
});

describe('latestTelemetry', () => {
  it('returns null when there are no items', () => {
    expect(latestTelemetry([])).toBeNull();
  });

  it('picks the newest valid timestamp regardless of list order', () => {
    const older = item('2026-10-10T12:00:00Z', { temperature: 20 });
    const newer = item('2026-10-10T12:01:00Z', { temperature: 22 });

    expect(latestTelemetry([newer, older])).toBe(newer);
    expect(latestTelemetry([older, newer])).toBe(newer);
  });

  it('ignores items with invalid timestamps', () => {
    const valid = item('2026-10-10T12:00:00Z');

    expect(latestTelemetry([item('not-a-date'), valid])).toBe(valid);
    expect(latestTelemetry([item('not-a-date')])).toBeNull();
  });
});

describe('isDeviceOnline', () => {
  const now = Date.parse('2026-10-10T12:00:00Z');

  it('is online inside the 60 second window', () => {
    const last = item(
      new Date(now - DEVICE_ONLINE_WINDOW_MS + 1000).toISOString(),
    );

    expect(isDeviceOnline(last, now)).toBe(true);
  });

  it('is offline exactly at the window boundary', () => {
    const last = item(new Date(now - DEVICE_ONLINE_WINDOW_MS).toISOString());

    expect(isDeviceOnline(last, now)).toBe(false);
  });

  it('is offline when telemetry is older than the window', () => {
    const last = item(
      new Date(now - DEVICE_ONLINE_WINDOW_MS - 1000).toISOString(),
    );

    expect(isDeviceOnline(last, now)).toBe(false);
  });

  it('is offline without telemetry or with an invalid timestamp', () => {
    expect(isDeviceOnline(null, now)).toBe(false);
    expect(isDeviceOnline(item('not-a-date'), now)).toBe(false);
  });

  it('is offline when telemetry is in the future', () => {
    const last = item(new Date(now + DEVICE_ONLINE_WINDOW_MS).toISOString());

    expect(isDeviceOnline(last, now)).toBe(false);
  });
});

describe('formatTelemetryValue', () => {
  it('formats scalar payload entries in order', () => {
    expect(
      formatTelemetryValue({
        temperature: 24.5,
        humidity: 55,
        status: 'ok',
        alarm: false,
      }),
    ).toBe('temperature: 24,5 · humidity: 55 · status: ok · alarm: false');
  });

  it('rounds floating point noise with pt-BR formatting', () => {
    expect(
      formatTelemetryValue({
        temperature: 24.100000001,
        humidity: 55.25,
      }),
    ).toBe('temperature: 24,1 · humidity: 55,25');
  });

  it('ignores nested objects and arrays', () => {
    expect(
      formatTelemetryValue({
        nested: { value: 1 },
        list: [1, 2],
      }),
    ).toBe('—');
  });

  it('returns a dash for a non-object payload', () => {
    expect(
      formatTelemetryValue('oops' as unknown as Record<string, unknown>),
    ).toBe('—');
    expect(
      formatTelemetryValue([1, 2] as unknown as Record<string, unknown>),
    ).toBe('—');
  });

  it('returns a dash for an empty payload', () => {
    expect(formatTelemetryValue({})).toBe('—');
  });
});
