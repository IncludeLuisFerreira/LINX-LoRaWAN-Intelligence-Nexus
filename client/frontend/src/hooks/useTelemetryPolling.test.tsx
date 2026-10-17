import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from 'vitest';
import { act, render } from '@testing-library/react';
import {
  POLL_LIMIT,
  useTelemetryPolling,
} from './useTelemetryPolling';
import { telemetryService, type TelemetryItem } from '../services/telemetry';

vi.mock('../services/telemetry', () => ({
  telemetryService: { history: vi.fn() },
}));

const mockedHistory = telemetryService.history as unknown as Mock;

const item = (time: string): TelemetryItem => ({
  time,
  dev_eui: 'aabbccddeeff0011',
  payload: { temperature: 20 },
  rssi: null,
  snr: null,
  app_id: 'app-1',
  event_type: 'up',
});

function Probe({
  devEui,
  enabled,
  onItem,
}: {
  devEui: string;
  enabled: boolean;
  onItem: (item: TelemetryItem) => void;
}) {
  useTelemetryPolling(devEui, enabled, onItem);
  return null;
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('useTelemetryPolling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => vi.useRealTimers());

  it('does not poll while disabled', async () => {
    const onItem = vi.fn();
    render(<Probe devEui="aabb" enabled={false} onItem={onItem} />);

    await advance(15000);

    expect(mockedHistory).not.toHaveBeenCalled();
    expect(onItem).not.toHaveBeenCalled();
  });

  it('polls GET /telemetry with the batch limit every 5s when enabled', async () => {
    const latest = item('2026-01-01T00:05:00Z');
    mockedHistory.mockResolvedValue({ items: [latest], next_cursor: null });
    const onItem = vi.fn();
    render(<Probe devEui="aabb" enabled onItem={onItem} />);

    await advance(5000);
    expect(mockedHistory).toHaveBeenCalledWith('aabb', { limit: POLL_LIMIT });
    expect(onItem).toHaveBeenCalledWith(latest);

    await advance(5000);
    expect(mockedHistory).toHaveBeenCalledTimes(2);
  });

  it('delivers every item in the response regardless of order', async () => {
    const older = item('2026-01-01T00:00:00Z');
    const newer = item('2026-01-03T00:00:00Z');
    mockedHistory.mockResolvedValue({
      items: [older, newer],
      next_cursor: null,
    });
    const onItem = vi.fn();
    render(<Probe devEui="aabb" enabled onItem={onItem} />);

    await advance(5000);

    expect(onItem).toHaveBeenCalledWith(older);
    expect(onItem).toHaveBeenCalledWith(newer);
    expect(onItem).toHaveBeenCalledTimes(2);
  });

  it('keeps polling when the fetch rejects', async () => {
    mockedHistory.mockRejectedValue(new Error('offline'));
    const onItem = vi.fn();
    render(<Probe devEui="aabb" enabled onItem={onItem} />);

    await advance(10000);

    expect(mockedHistory).toHaveBeenCalledTimes(2);
    expect(onItem).not.toHaveBeenCalled();
  });

  it('does nothing without a devEui', async () => {
    const onItem = vi.fn();
    render(<Probe devEui="" enabled onItem={onItem} />);

    await advance(10000);

    expect(mockedHistory).not.toHaveBeenCalled();
  });

  it('stops polling after unmount', async () => {
    mockedHistory.mockResolvedValue({ items: [], next_cursor: null });
    const { unmount } = render(
      <Probe devEui="aabb" enabled onItem={vi.fn()} />,
    );

    await advance(5000);
    expect(mockedHistory).toHaveBeenCalledTimes(1);

    unmount();
    await advance(10000);
    expect(mockedHistory).toHaveBeenCalledTimes(1);
  });

  it('restarts the timer when the devEui changes', async () => {
    mockedHistory.mockResolvedValue({ items: [], next_cursor: null });
    const { rerender } = render(
      <Probe devEui="aabb" enabled onItem={vi.fn()} />,
    );

    await advance(5000);
    expect(mockedHistory).toHaveBeenLastCalledWith('aabb', { limit: POLL_LIMIT });

    rerender(<Probe devEui="ccdd" enabled onItem={vi.fn()} />);
    await advance(5000);
    expect(mockedHistory).toHaveBeenLastCalledWith('ccdd', { limit: POLL_LIMIT });
  });
});
