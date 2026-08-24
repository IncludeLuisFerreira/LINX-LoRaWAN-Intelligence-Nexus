import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TelemetryRow } from '../types'

const PAGE_SIZE = 20

const fmtTime = (iso: string): string =>
  new Date(iso).toLocaleString('pt-BR', { hour12: false })

export function HistoryTable() {
  const [rows, setRows] = useState<TelemetryRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api
      .telemetry({ deviceEui: search || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => {
        setRows(r.rows)
        setTotal(r.total)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [page, search])

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-white">Histórico</h2>
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(0)
          }}
          placeholder="Buscar por device EUI..."
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 outline-none focus:border-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500 dark:border-gray-700 dark:text-gray-400">
              <th className="px-3 py-2">Horário</th>
              <th className="px-3 py-2">Device</th>
              <th className="px-3 py-2">LDR</th>
              <th className="px-3 py-2">Bateria</th>
              <th className="px-3 py-2">RSSI</th>
              <th className="px-3 py-2">SNR</th>
              <th className="px-3 py-2">FCnt</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-gray-100 text-gray-700 dark:border-gray-800 dark:text-gray-300"
              >
                <td className="px-3 py-2 whitespace-nowrap">{fmtTime(row.timestamp)}</td>
                <td className="px-3 py-2">
                  <span className="font-medium text-gray-900 dark:text-white">{row.device_name}</span>
                  <span className="ml-1 font-mono text-xs text-gray-500">{row.device_eui}</span>
                </td>
                <td className="px-3 py-2">{row.payload ? (row.payload as { object?: { ldr_value?: number } }).object?.ldr_value ?? '—' : '—'}</td>
                <td className="px-3 py-2">{row.battery_level?.toFixed(2) ?? '—'}</td>
                <td className="px-3 py-2">{row.rssi ?? '—'}</td>
                <td className="px-3 py-2">{row.snr ?? '—'}</td>
                <td className="px-3 py-2">{row.fcnt ?? '—'}</td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-gray-500">
                  Nenhum registro encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {total} registro(s) · página {page + 1}/{pages}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-lg border border-gray-300 px-3 py-1 text-sm disabled:opacity-40 dark:border-gray-600"
          >
            Anterior
          </button>
          <button
            onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
            disabled={page >= pages - 1}
            className="rounded-lg border border-gray-300 px-3 py-1 text-sm disabled:opacity-40 dark:border-gray-600"
          >
            Próxima
          </button>
        </div>
      </div>
    </div>
  )
}
