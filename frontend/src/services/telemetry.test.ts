import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import {
  telemetryService,
  numericMetrics,
  buildSeries,
  mergeSeries,
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
