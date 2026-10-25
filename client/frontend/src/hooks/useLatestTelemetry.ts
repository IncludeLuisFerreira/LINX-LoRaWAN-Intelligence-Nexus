import { useEffect, useState } from 'react';
import type { DeviceOutput } from '../services/device';
import { telemetryService, type TelemetryItem } from '../services/telemetry';
import { latestTelemetry } from '../utils/deviceTelemetry';

export const LATEST_TELEMETRY_POLL_INTERVAL_MS = 30_000;

interface LatestTelemetryState {
  key: string;
  items: Record<string, TelemetryItem | null>;
}

const EMPTY_LATEST_TELEMETRY: Record<string, TelemetryItem | null> = {};
const INITIAL_STATE: LatestTelemetryState = {
  key: '',
  items: EMPTY_LATEST_TELEMETRY,
};

export function useLatestTelemetry(
  devices: DeviceOutput[],
  intervalMs: number = LATEST_TELEMETRY_POLL_INTERVAL_MS,
): Record<string, TelemetryItem | null> {
  const devEuis = [...new Set(devices.map((device) => device.dev_eui))].sort();
  const deviceKey = JSON.stringify(devEuis);
  const [state, setState] = useState<LatestTelemetryState>(INITIAL_STATE);

  useEffect(() => {
    const currentDevEuis = JSON.parse(deviceKey) as string[];
    if (currentDevEuis.length === 0) return;

    let active = true;
    let inFlight = false;

    const fetchAll = async () => {
      if (inFlight) return;
      inFlight = true;

      try {
        const results = await Promise.allSettled(
          currentDevEuis.map((devEui) =>
            telemetryService.history(devEui, { limit: 1 }),
          ),
        );
        if (!active) return;

        setState((previous) => {
          const base = previous.key === deviceKey ? previous.items : {};
          const items: Record<string, TelemetryItem | null> = {};

          currentDevEuis.forEach((devEui, index) => {
            const result = results[index];
            items[devEui] =
              result.status === 'fulfilled'
                ? latestTelemetry(result.value.items)
                : (base[devEui] ?? null);
          });

          return { key: deviceKey, items };
        });
      } finally {
        inFlight = false;
      }
    };

    void fetchAll();
    const id = setInterval(() => {
      void fetchAll();
    }, intervalMs);

    return () => {
      active = false;
      clearInterval(id);
    };
  }, [deviceKey, intervalMs]);

  return state.key === deviceKey ? state.items : EMPTY_LATEST_TELEMETRY;
}
