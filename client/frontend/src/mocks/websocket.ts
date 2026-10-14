import { ws } from 'msw';

export const telemetrySocket = ws.link('*/ws/telemetry/:appId');

export interface MockTelemetryMessage {
  time: string;
  dev_eui: string;
  payload: { temperature: number };
  rssi: number;
  snr: number;
  app_id: string;
  event_type: string;
}

export function buildMockTelemetryMessage(appId: string): MockTelemetryMessage {
  return {
    time: new Date().toISOString(),
    dev_eui: 'aabbccddeeff0000',
    payload: { temperature: 20 + Math.random() * 5 },
    rssi: -70,
    snr: 7,
    app_id: appId,
    event_type: 'up',
  };
}

export const websocketHandlers = [
  telemetrySocket.addEventListener('connection', ({ client, params }) => {
    const appId = String(params.appId);
    const timer = setInterval(() => {
      client.send(JSON.stringify(buildMockTelemetryMessage(appId)));
    }, 2000);
    client.addEventListener('close', () => clearInterval(timer));
  }),
];
