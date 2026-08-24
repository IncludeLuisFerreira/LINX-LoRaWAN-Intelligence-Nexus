import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { DeviceStatus, Reading } from '../types'

interface DeviceCardsProps {
  buffer: Record<string, Reading[]>
  selectedDevice?: string
  onSelect: (eui: string) => void
}

const fmtTime = (iso: string): string =>
  new Date(iso).toLocaleString('pt-BR', { hour12: false })

export function DeviceCards({ buffer, selectedDevice, onSelect }: DeviceCardsProps) {
  const [devices, setDevices] = useState<DeviceStatus[]>([])

  useEffect(() => {
    api
      .devices()
      .then((r) => setDevices(r.devices))
      .catch(() => {})
  }, [])

  const allEuis = Array.from(new Set([...devices.map((d) => d.device_eui), ...Object.keys(buffer)]))

  if (allEuis.length === 0) {
    return (
      <div className="rounded-xl border-2 border-dashed border-gray-300 p-10 text-center text-gray-500 dark:border-gray-700 dark:text-gray-400">
        Aguardando primeiro uplink do dispositivo...
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {allEuis.map((eui) => {
        const device = devices.find((d) => d.device_eui === eui)
        const readings = buffer[eui] ?? []
        const reading = readings[readings.length - 1]
        const online = device ? device.online : Boolean(reading)
        const active = selectedDevice === eui

        return (
          <button
            key={eui}
            onClick={() => onSelect(eui)}
            className={`rounded-xl border p-4 text-left shadow-sm transition-colors ${
              active
                ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-900/20'
                : 'border-gray-200 bg-white hover:border-blue-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-500'
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">{device?.device_name ?? reading?.deviceName ?? eui}</p>
                <p className="font-mono text-xs text-gray-500 dark:text-gray-400">{eui}</p>
              </div>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                  online
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                    : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-green-500' : 'bg-red-500'}`} />
                {online ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">LDR</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.metrics.ldr_value?.toFixed(0) ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Bateria</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.metrics.battery_level?.toFixed(2) ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">RSSI</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.rssi != null ? `${reading.rssi} dBm` : '—'}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">SNR</p>
                <p className="font-medium text-gray-900 dark:text-white">
                  {reading?.snr != null ? `${reading.snr} dB` : '—'}
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
              {reading ? fmtTime(reading.timestamp) : device ? fmtTime(device.last_seen_at) : '—'}
            </p>
          </button>
        )
      })}
    </div>
  )
}
