import { useEffect, useRef } from 'react';
import {
  buildTelemetrySocketUrl,
  parseTelemetryMessage,
  type TelemetryItem,
} from '../services/telemetry';

export function useTelemetrySocket(
  appId: string,
  onMessage: (item: TelemetryItem) => void,
): void {
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!appId) return;
    const ws = new WebSocket(buildTelemetrySocketUrl(appId));
    ws.onmessage = (event) => {
      const item = parseTelemetryMessage(event.data);
      if (item) onMessageRef.current(item);
    };
    ws.onerror = () => {};
    return () => ws.close();
  }, [appId]);
}
