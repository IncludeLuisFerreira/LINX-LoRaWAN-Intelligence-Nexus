// frontend/src/hooks/useTelemetryPolling.ts
import { useEffect, useState } from 'react';
import { api } from '../services/api'; // Certifique-se de importar o cliente Axios configurado

interface UseTelemetryPollingParams {
  wsOnline: boolean;
  devEui?: string;
  onDataReceived?: (data: any) => void;
}

export function useTelemetryPolling({
  wsOnline,
  devEui,
  onDataReceived,
}: UseTelemetryPollingParams) {
  const [telemetry, setTelemetry] = useState<any>(null);

  useEffect(() => {
    // Polling ativo apenas quando o WebSocket estiver offline
    if (wsOnline || !devEui) return;

    const fetchTelemetry = async () => {
      try {
        const response = await api.get(`/telemetry/${devEui}?limit=1`);
        const latestData = response.data;
        setTelemetry(latestData);
        if (onDataReceived) {
          onDataReceived(latestData);
        }
      } catch (error) {
        console.error('Erro no polling de telemetria:', error);
      }
    };

    // Executa imediatamente no fallback e depois a cada 5s (5000ms)
    fetchTelemetry();
    const id = setInterval(fetchTelemetry, 5000);

    return () => clearInterval(id);
  }, [wsOnline, devEui, onDataReceived]);

  return telemetry;
}
