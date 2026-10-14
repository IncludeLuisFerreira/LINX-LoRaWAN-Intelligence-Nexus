import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import {
  telemetryService,
  numericMetrics,
  buildSeries,
  mergeSeries,
  buildTelemetrySocketUrl,
  parseTelemetryMessage,
  appendItem,
  type TelemetryItem,
} from './telemetry';

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mocked = api as unknown as Record<'get', Mock>;

const item = (
  time: string,
  payload: Record<string, unknown>,
): TelemetryItem => ({
  time,
  dev_eui: 'aabbccddeeff0011',
  payload,
  rssi: -70,
  snr: 7.5,
  app_id: 'app-1',
  event_type: 'up',
});

describe('telemetryService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('requests history with dev_eui and default limit', async () => {
    mocked.get.mockResolvedValue({ data: { items: [], next_cursor: null } });

    await telemetryService.history('aabbccddeeff0011');

    expect(mocked.get).toHaveBeenCalledWith('/telemetry', {
      params: {
        dev_eui: 'aabbccddeeff0011',
        limit: 100,
        before: undefined,
      },
    });
  });

  it('forwards limit and before cursor', async () => {
    mocked.get.mockResolvedValue({ data: { items: [], next_cursor: null } });

    await telemetryService.history('aabbccddeeff0011', {
      limit: 25,
      before: '2026-01-01T00:00:00Z',
    });

    expect(mocked.get).toHaveBeenCalledWith('/telemetry', {
      params: {
        dev_eui: 'aabbccddeeff0011',
        limit: 25,
        before: '2026-01-01T00:00:00Z',
      },
    });
  });
});

describe('numericMetrics', () => {
  it('lists numeric payload keys in order, ignoring non-numbers', () => {
    const metrics = numericMetrics([
      item('2026-01-01T00:00:00Z', { temperature: 25, label: 'x' }),
      item('2026-01-01T00:01:00Z', { temperature: 26, humidity: 50 }),
    ]);

    expect(metrics).toEqual(['temperature', 'humidity']);
  });

  it('returns an empty list when there is no numeric value', () => {
    expect(numericMetrics([item('t', { label: 'x' })])).toEqual([]);
  });
});

describe('buildSeries', () => {
  it('maps the metric to { time, value } sorted ascending', () => {
    const series = buildSeries(
      [
        item('2026-01-01T00:02:00Z', { temperature: 22 }),
        item('2026-01-01T00:00:00Z', { temperature: 20 }),
      ],
      'temperature',
    );

    expect(series).toEqual([
      { time: '2026-01-01T00:00:00Z', value: 20 },
      { time: '2026-01-01T00:02:00Z', value: 22 },
    ]);
  });

  it('drops items without a numeric value for the metric', () => {
    const series = buildSeries(
      [
        item('2026-01-01T00:00:00Z', { temperature: 'n/a' }),
        item('2026-01-01T00:01:00Z', { humidity: 30 }),
      ],
      'temperature',
    );

    expect(series).toEqual([]);
  });

  it('returns an empty series for empty input', () => {
    expect(buildSeries([], 'temperature')).toEqual([]);
  });

  it('keeps a single point as-is', () => {
    const series = buildSeries(
      [item('2026-01-01T00:00:00Z', { temperature: 20 })],
      'temperature',
    );

    expect(series).toHaveLength(1);
  });
});

describe('mergeSeries', () => {
  it('merges points by time with one key per series', () => {
    const rows = mergeSeries([
      { key: 'a', label: 'A', data: [{ time: 't1', value: 1 }] },
      {
        key: 'b',
        label: 'B',
        data: [
          { time: 't1', value: 2 },
          { time: 't2', value: 3 },
        ],
      },
    ]);

    expect(rows).toEqual([
      { time: 't1', a: 1, b: 2 },
      { time: 't2', b: 3 },
    ]);
  });
});

describe('buildTelemetrySocketUrl', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('uses VITE_WS_URL as base when defined', () => {
    vi.stubEnv('VITE_WS_URL', 'wss://ws.example.com');
    expect(buildTelemetrySocketUrl('app-1')).toBe(
      'wss://ws.example.com/ws/telemetry/app-1',
    );
  });

  it('derives wss from https location', () => {
    vi.stubEnv('VITE_WS_URL', '');
    vi.stubGlobal('location', { protocol: 'https:', host: 'linx.test' });
    expect(buildTelemetrySocketUrl('app-2')).toBe(
      'wss://linx.test/ws/telemetry/app-2',
    );
  });

  it('derives ws from http location', () => {
    vi.stubEnv('VITE_WS_URL', '');
    vi.stubGlobal('location', { protocol: 'http:', host: 'localhost:5173' });
    expect(buildTelemetrySocketUrl('app-3')).toBe(
      'ws://localhost:5173/ws/telemetry/app-3',
    );
  });
});

describe('parseTelemetryMessage', () => {
  it('parses a valid JSON string into a TelemetryItem', () => {
    const raw =
      '{"time":"2026-01-01T00:00:00Z","dev_eui":"aabb","payload":{"temperature":21},"rssi":-70,"snr":7,"app_id":"app-1","event_type":"up"}';
    expect(parseTelemetryMessage(raw)).toEqual({
      time: '2026-01-01T00:00:00Z',
      dev_eui: 'aabb',
      payload: { temperature: 21 },
      rssi: -70,
      snr: 7,
      app_id: 'app-1',
      event_type: 'up',
    });
  });

  it('returns null on invalid JSON', () => {
    expect(parseTelemetryMessage('{not json')).toBeNull();
  });

  it('returns null when a required field is missing', () => {
    expect(parseTelemetryMessage('{"dev_eui":"aabb","payload":{}}')).toBeNull();
    expect(parseTelemetryMessage('{"time":"t","payload":{}}')).toBeNull();
    expect(parseTelemetryMessage('{"time":"t","dev_eui":"aabb"}')).toBeNull();
  });

  it('defaults optional fields when absent', () => {
    expect(
      parseTelemetryMessage('{"time":"t","dev_eui":"aabb","payload":{}}'),
    ).toEqual({
      time: 't',
      dev_eui: 'aabb',
      payload: {},
      rssi: null,
      snr: null,
      app_id: '',
      event_type: '',
    });
  });
});

describe('appendItem', () => {
  const point = (time: string, devEui = 'aabb', eventType = 'up') => ({
    time,
    dev_eui: devEui,
    payload: { temperature: 1 },
    rssi: null,
    snr: null,
    app_id: 'app-1',
    event_type: eventType,
  });

  it('appends a new item sorted by time', () => {
    const items = [point('2026-01-02T00:00:00Z')];
    const result = appendItem(items, point('2026-01-01T00:00:00Z'));
    expect(result.map((i) => i.time)).toEqual([
      '2026-01-01T00:00:00Z',
      '2026-01-02T00:00:00Z',
    ]);
  });

  it('ignores a duplicate by (dev_eui, time, event_type)', () => {
    const items = [point('2026-01-01T00:00:00Z')];
    const result = appendItem(items, point('2026-01-01T00:00:00Z'));
    expect(result).toHaveLength(1);
    expect(result).toBe(items);
  });

  it('keeps different event_type at the same time', () => {
    const items = [point('2026-01-01T00:00:00Z', 'aabb', 'up')];
    const result = appendItem(
      items,
      point('2026-01-01T00:00:00Z', 'aabb', 'status'),
    );
    expect(result).toHaveLength(2);
  });

  it('dedupes the same instant written with different offset formats', () => {
    const items = [point('2026-01-01T00:00:00Z')];
    const result = appendItem(items, point('2026-01-01T00:00:00+00:00'));
    expect(result).toBe(items);
    expect(result).toHaveLength(1);
  });

  it('does not collapse an unparseable time with a valid one', () => {
    const items = [point('garbage')];
    const result = appendItem(items, point('2026-01-01T00:00:00Z'));
    expect(result).toHaveLength(2);
  });

  it('dedupes exact duplicates that are not valid dates', () => {
    const items = [point('garbage')];
    expect(appendItem(items, point('garbage'))).toBe(items);
  });
});
