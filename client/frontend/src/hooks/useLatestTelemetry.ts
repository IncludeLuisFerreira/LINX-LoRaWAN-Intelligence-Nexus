import { useEffect, useState } from 'react';
import type { DeviceOutput } from '../services/device';
import { telemetryService, type TelemetryItem } from '../services/telemetry';
import { latestTelemetry } from '../utils/deviceTelemetry';

export const LATEST_TELEMETRY_POLL_INTERVAL_MS = 30_000;

const EMPTY_LATEST_TELEMETRY: Record<string, TelemetryItem | null> = {};

export function useLatestTelemetry(
  devices: DeviceOutput[],
  intervalMs: number = LATEST_TELEMETRY_POLL_INTERVAL_MS,
): Record<string, TelemetryItem | null> {
  const deviceKey = [...new Set(devices.map((device) => device.dev_eui))]
    .sort()
    .join('|');
  const [latest, setLatest] = useState<Record<string, TelemetryItem | null>>(
    {},
  );

  useEffect(() => {
    const devEuis = deviceKey ? deviceKey.split('|') : [];
    if (devEuis.length === 0) return;

    let active = true;

    const fetchAll = async () => {
      const results = await Promise.allSettled(
        devEuis.map((devEui) => telemetryService.history(devEui, { limit: 1 })),
      );
      if (!active) return;

      const next: Record<string, TelemetryItem | null> = {};
      devEuis.forEach((devEui, index) => {
        const result = results[index];
        next[devEui] =
          result.status === 'fulfilled'
            ? latestTelemetry(result.value.items)
            : null;
      });
      setLatest(next);
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

  return deviceKey ? latest : EMPTY_LATEST_TELEMETRY;
}
