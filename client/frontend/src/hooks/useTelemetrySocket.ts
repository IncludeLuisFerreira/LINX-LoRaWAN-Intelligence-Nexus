import { useEffect, useRef, useState } from 'react';
import {
  buildTelemetrySocketUrl,
  parseTelemetryMessage,
  type TelemetryItem,
} from '../services/telemetry';

export type TelemetrySocketStatus = 'connecting' | 'online' | 'offline';

/** Tempo máximo parado em `connecting` antes de cair para `offline`. */
export const SOCKET_CONNECT_TIMEOUT_MS = 5000;

interface SocketState {
  appId: string;
  status: TelemetrySocketStatus;
}

export function useTelemetrySocket(
  appId: string,
  onMessage: (item: TelemetryItem) => void,
): TelemetrySocketStatus {
  const onMessageRef = useRef(onMessage);
  const [state, setState] = useState<SocketState>(() => ({
    appId,
    status: 'connecting',
  }));

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!appId) return;

    const ws = new WebSocket(buildTelemetrySocketUrl(appId));
    // Só este efeito pode reportar status enquanto estiver ativo. Eventos de um
    // socket já substituído (StrictMode re-monta o efeito) devem ser ignorados,
    // senão um `onclose` atrasado sobrescreve o status do socket atual.
    let active = true;
    const update = (status: TelemetrySocketStatus) => {
      if (active) setState({ appId, status });
    };

    // Se a conexão travar sem onopen/onerror/onclose, libera o fallback REST.
    let connectTimeout: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      connectTimeout = null;
      update('offline');
    }, SOCKET_CONNECT_TIMEOUT_MS);
    const clearConnectTimeout = () => {
      if (connectTimeout) {
        clearTimeout(connectTimeout);
        connectTimeout = null;
      }
    };

    ws.onopen = () => {
      clearConnectTimeout();
      update('online');
    };
    ws.onmessage = (event) => {
      const item = parseTelemetryMessage(event.data);
      if (item) onMessageRef.current(item);
    };
    ws.onerror = () => {
      clearConnectTimeout();
      update('offline');
    };
    ws.onclose = () => {
      clearConnectTimeout();
      update('offline');
    };

    return () => {
      active = false;
      clearConnectTimeout();
      ws.close();
    };
  }, [appId]);

  // Enquanto o estado pertence a outro appId, ainda não há veredito: connecting.
  return state.appId === appId ? state.status : 'connecting';
}
