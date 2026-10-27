// frontend/src/hooks/useTelemetrySocket.ts
import { useState, useEffect, useRef } from 'react';

export function useTelemetrySocket(devEui: string) {
  const [data, setData] = useState<any>(null);
  const [wsOnline, setWsOnline] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!devEui) return;

    const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/telemetry/${devEui}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsOnline(true);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setData(payload);
      } catch (err) {
        console.error('Erro ao processar mensagem do WS', err);
      }
    };

    ws.onerror = () => {
      setWsOnline(false);
    };

    ws.onclose = () => {
      setWsOnline(false);
    };

    return () => {
      ws.close();
      setWsOnline(false);
    };
  }, [devEui]);

  return { data, wsOnline };
}
