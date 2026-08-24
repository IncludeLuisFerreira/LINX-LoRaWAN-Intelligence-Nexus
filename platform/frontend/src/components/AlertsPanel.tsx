import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AlertRow } from '../types'

const fmtTime = (iso: string): string =>
  new Date(iso).toLocaleString('pt-BR', { hour12: false })

export function AlertsPanel() {
  const [alerts, setAlerts] = useState<AlertRow[]>([])

  useEffect(() => {
    api
      .alerts(10)
      .then((r) => setAlerts(r.rows))
      .catch(() => {})
  }, [])

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-3 font-semibold text-gray-900 dark:text-white">Alertas recentes</h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Nenhum alerta registrado.</p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((a) => (
            <li
              key={a.id}
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
            >
              <span className="font-semibold">{a.device_eui}</span> · {a.metric} = {a.value}{' '}
              (limite {a.metric} {a.threshold}) · {fmtTime(a.sent_at)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
