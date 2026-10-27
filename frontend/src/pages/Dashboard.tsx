import { useState } from 'react';
import { useTelemetrySocket } from '../hooks/useTelemetrySocket';
import { useTelemetryPolling } from '../hooks/useTelemetryPolling';

export function TelemetryChart({ devEui }: { devEui: string }) {
  const [chartData, setChartData] = useState<any[]>([]);
  const { wsOnline } = useTelemetrySocket(devEui);

  // Fallback via Polling a cada 5s quando WebSocket estiver offline
  useTelemetryPolling({
    wsOnline,
    devEui,
    onDataReceived: (polledData) => {
      // Atualiza o gráfico com os dados recebidos via polling
      setChartData((prev) => [...prev, polledData]);
    },
  });

  return (
    <div>
      <div className="status-indicator">
        Status WS: {wsOnline ? '🟢 Conectado' : '🔴 Offline (Polling Ativo 5s)'}
      </div>

      {/* Uso da variável chartData para eliminar o aviso do TS */}
      <div className="telemetry-data">
        <h3>Histórico de Telemetria ({chartData.length} registros)</h3>
        <pre>{JSON.stringify(chartData, null, 2)}</pre>
      </div>
    </div>
  );
}

export default function Dashboard() {
  // Exemplo de uso - em produção viria dos props/route params
  const devEui = '1234567890ABCDEF';
  return (
    <div className="p-8 text-white">
      <h1 className="text-2xl mb-4">Dashboard do App</h1>
      <TelemetryChart devEui={devEui} />
    </div>
  );
}
