import { describe, expect, it } from 'vitest';
import { buildMockTelemetryMessage } from './websocket';

describe('buildMockTelemetryMessage', () => {
  it('echoes the connection app_id so the dashboard does not filter it out', () => {
    const appId = crypto.randomUUID();
    const message = buildMockTelemetryMessage(appId);

    expect(message.app_id).toBe(appId);
  });

  it('produces a valid telemetry frame', () => {
    const message = buildMockTelemetryMessage('app-123');

    expect(message.dev_eui).toBe('aabbccddeeff0000');
    expect(message.event_type).toBe('up');
    expect(typeof message.payload.temperature).toBe('number');
    expect(typeof message.time).toBe('string');
  });
});
