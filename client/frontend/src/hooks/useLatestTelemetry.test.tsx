import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../mocks/handlers';
import type { DeviceOutput } from '../services/device';
import type { TelemetryItem } from '../services/telemetry';
import { useLatestTelemetry } from './useLatestTelemetry';

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function device(devEui: string): DeviceOutput {
  return {
    id: `id-${devEui}`,
    dev_eui: devEui,
    app_id: 'app-1',
    join_eui: '1122334455667788',
    device_profile_id: 'profile-1',
    nickname: null,
    created_at: '2026-10-10T12:00:00Z',
    updated_at: '2026-10-10T12:00:00Z',
  };
}

function telemetry(devEui: string, value: number): TelemetryItem {
  return {
    time: new Date().toISOString(),
    dev_eui: devEui,
    payload: { value },
    rssi: -70,
    snr: 7.5,
    app_id: 'app-1',
    event_type: 'up',
  };
}

describe('useLatestTelemetry', () => {
  it('loads the latest telemetry for every device', async () => {
    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const params = new URL(request.url).searchParams;
        const devEui = params.get('dev_eui') ?? '';
        expect(params.get('limit')).toBe('1');
        return HttpResponse.json({
          items: [telemetry(devEui, devEui === 'aabbccddeeff0001' ? 21 : 35)],
          next_cursor: null,
        });
      }),
    );

    const { result } = renderHook(() =>
      useLatestTelemetry([
        device('aabbccddeeff0001'),
        device('aabbccddeeff0002'),
      ]),
    );

    await waitFor(() => {
      expect(result.current['aabbccddeeff0001']?.payload).toEqual({
        value: 21,
      });
      expect(result.current['aabbccddeeff0002']?.payload).toEqual({
        value: 35,
      });
    });
  });

  it('keeps successful devices when one telemetry request fails', async () => {
    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const devEui = new URL(request.url).searchParams.get('dev_eui');
        if (devEui === 'aabbccddeeff0002') {
          return HttpResponse.json({ detail: 'boom' }, { status: 500 });
        }
        return HttpResponse.json({
          items: [telemetry(devEui ?? '', 21)],
          next_cursor: null,
        });
      }),
    );

    const { result } = renderHook(() =>
      useLatestTelemetry([
        device('aabbccddeeff0001'),
        device('aabbccddeeff0002'),
      ]),
    );

    await waitFor(() =>
      expect(result.current['aabbccddeeff0001']?.payload).toEqual({
        value: 21,
      }),
    );
    expect(result.current['aabbccddeeff0002']).toBeNull();
  });

  it('refetches on the polling interval', async () => {
    let calls = 0;
    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        calls += 1;
        const devEui = new URL(request.url).searchParams.get('dev_eui') ?? '';
        return HttpResponse.json({
          items: [
            {
              ...telemetry(devEui, calls),
              time: new Date(Date.now() + calls * 1000).toISOString(),
            },
          ],
          next_cursor: null,
        });
      }),
    );

    const { result } = renderHook(() =>
      useLatestTelemetry([device('aabbccddeeff0001')], 20),
    );

    await waitFor(
      () =>
        expect(
          result.current['aabbccddeeff0001']?.payload.value,
        ).toBeGreaterThanOrEqual(2),
      { timeout: 2000 },
    );
  });

  it('keeps the previous reading when a later poll fails', async () => {
    const devEui = 'aabbccddeeff0003';
    let calls = 0;

    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        calls += 1;
        const requested =
          new URL(request.url).searchParams.get('dev_eui') ?? '';
        if (requested === devEui && calls >= 2) {
          return HttpResponse.json({ detail: 'boom' }, { status: 500 });
        }
        return HttpResponse.json({
          items: [telemetry(requested, 21)],
          next_cursor: null,
        });
      }),
    );

    const { result } = renderHook(() =>
      useLatestTelemetry([device(devEui)], 10),
    );

    await waitFor(() =>
      expect(result.current[devEui]?.payload).toEqual({ value: 21 }),
    );
    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(2));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    expect(result.current[devEui]?.payload).toEqual({ value: 21 });
  });

  it('skips polling ticks while the previous wave is still in flight', async () => {
    const devEui = 'aabbccddeeff0004';
    let calls = 0;
    let releaseFirst: (() => void) | undefined;

    server.use(
      http.get('*/api/v1/telemetry', () => {
        calls += 1;
        if (calls === 1) {
          return new Promise<Response>((resolve) => {
            releaseFirst = () =>
              resolve(
                HttpResponse.json({
                  items: [telemetry(devEui, 1)],
                  next_cursor: null,
                }),
              );
          });
        }
        return HttpResponse.json({
          items: [telemetry(devEui, calls)],
          next_cursor: null,
        });
      }),
    );

    const { result } = renderHook(() =>
      useLatestTelemetry([device(devEui)], 10),
    );

    await waitFor(() => expect(calls).toBe(1));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 60));
    });
    expect(calls).toBe(1);

    releaseFirst?.();
    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(2));
    expect(result.current[devEui]).not.toBeNull();
  });

  it('does not split dev_eui values on the legacy delimiter', async () => {
    const requested: string[] = [];

    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const devEui = new URL(request.url).searchParams.get('dev_eui') ?? '';
        requested.push(devEui);
        return HttpResponse.json({
          items: [telemetry(devEui, 1)],
          next_cursor: null,
        });
      }),
    );

    renderHook(() => useLatestTelemetry([device('a|b'), device('c')]));

    await waitFor(() =>
      expect(new Set(requested)).toEqual(new Set(['a|b', 'c'])),
    );
  });

  it('ignores an in-flight response from a device list after an app switch', async () => {
    const oldDevEui = 'aabbccddeeff0a0a';
    const newDevEui = 'aabbccddeeff0b0b';
    let releaseOld: (() => void) | undefined;

    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const devEui = new URL(request.url).searchParams.get('dev_eui') ?? '';
        if (devEui === oldDevEui) {
          return new Promise<Response>((resolve) => {
            releaseOld = () =>
              resolve(
                HttpResponse.json({
                  items: [telemetry(oldDevEui, 10)],
                  next_cursor: null,
                }),
              );
          });
        }
        return HttpResponse.json({
          items: [telemetry(devEui, 35)],
          next_cursor: null,
        });
      }),
    );

    const { result, rerender } = renderHook(
      ({ devices }: { devices: DeviceOutput[] }) => useLatestTelemetry(devices),
      { initialProps: { devices: [device(oldDevEui)] } },
    );

    await waitFor(() => expect(releaseOld).toBeDefined());
    rerender({ devices: [device(newDevEui)] });
    await waitFor(() =>
      expect(result.current[newDevEui]?.payload).toEqual({ value: 35 }),
    );

    releaseOld?.();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    expect(result.current[oldDevEui]).toBeUndefined();
    expect(result.current[newDevEui]?.payload).toEqual({ value: 35 });
  });

  it('exposes no entry until the first poll resolves', async () => {
    const devEui = 'aabbccddeeff0005';
    let release: (() => void) | undefined;

    server.use(
      http.get('*/api/v1/telemetry', () => {
        return new Promise<Response>((resolve) => {
          release = () =>
            resolve(
              HttpResponse.json({
                items: [telemetry(devEui, 21)],
                next_cursor: null,
              }),
            );
        });
      }),
    );

    const { result } = renderHook(() => useLatestTelemetry([device(devEui)]));

    await waitFor(() => expect(release).toBeDefined());
    expect(result.current[devEui]).toBeUndefined();

    release?.();
    await waitFor(() =>
      expect(result.current[devEui]?.payload).toEqual({ value: 21 }),
    );
  });
});
