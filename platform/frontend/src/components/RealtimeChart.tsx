import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Reading } from '../types'

const METRICS: Array<{ key: string; label: string }> = [
  { key: 'ldr_value', label: 'Luminosidade' },
  { key: 'temperature', label: 'Temperatura' },
  { key: 'humidity', label: 'Umidade' },
  { key: 'battery_level', label: 'Bateria' },
  { key: 'rssi', label: 'RSSI' },
  { key: 'snr', label: 'SNR' },
]

interface RealtimeChartProps {
  data: Reading[]
}

export function RealtimeChart({ data }: RealtimeChartProps) {
  const [metric, setMetric] = useState('ldr_value')

  const chartData = data.map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString('pt-BR', { hour12: false }),
    value:
      r.metrics[metric] ??
      (metric === 'rssi' ? r.rssi : metric === 'snr' ? r.snr : undefined),
  }))

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-white">Telemetria em tempo real</h2>
        <div className="flex flex-wrap gap-2">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                metric === m.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="time" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '8px',
              color: '#f9fafb',
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="value" name={metric} stroke="#3b82f6" dot={false} />
        </LineChart>
      </ResponsiveContainer>
      {data.length === 0 && (
        <p className="mt-2 text-center text-sm text-gray-500 dark:text-gray-400">
          Sem dados ainda — aguardando uplinks via WebSocket...
        </p>
      )}
    </div>
  )
}
