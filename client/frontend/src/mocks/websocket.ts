import { ws } from 'msw';

export const telemetrySocket = ws.link('*/ws/telemetry/:appId');

export const websocketHandlers = [
  telemetrySocket.addEventListener('connection', ({ client }) => {
    const timer = setInterval(() => {
      client.send(
        JSON.stringify({
          time: new Date().toISOString(),
          dev_eui: 'aabbccddeeff0000',
          payload: { temperature: 20 + Math.random() * 5 },
          rssi: -70,
          snr: 7,
          app_id: 'mock-app',
          event_type: 'up',
        }),
      );
    }, 2000);
    client.addEventListener('close', () => clearInterval(timer));
  }),
];
