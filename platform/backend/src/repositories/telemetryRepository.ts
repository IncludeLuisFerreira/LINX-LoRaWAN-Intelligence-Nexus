import { pool } from '../db/pool'
import type { Reading } from '../types'

export interface TelemetryRow {
  id: number
  device_eui: string
  device_name: string
  application_id: string
  temperature: number | null
  humidity: number | null
  battery_level: number | null
  rssi: number | null
  snr: number | null
  fcnt: number | null
  payload: unknown
  timestamp: string
}

const NUMERIC_COLUMNS = 11

export async function insertTelemetryBatch(readings: Reading[]): Promise<void> {
  if (readings.length === 0) return
  const values: unknown[] = []
  const rows: unknown[][] = []
  for (const r of readings) {
    rows.push([
      r.deviceEui,
      r.deviceName,
      r.applicationId,
      r.metrics.temperature ?? null,
      r.metrics.humidity ?? null,
      r.metrics.battery_level ?? null,
      r.rssi ?? null,
      r.snr ?? null,
      r.fCnt ?? null,
      JSON.stringify(r.raw),
      r.timestamp,
    ])
  }
  for (const row of rows) values.push(...row)
  const placeholders = rows
    .map((_, i) => {
      const base = i * NUMERIC_COLUMNS
      const parts: string[] = []
      for (let c = 1; c <= NUMERIC_COLUMNS; c++) parts.push(`$${base + c}`)
      return `(${parts.join(', ')})`
    })
    .join(', ')
  await pool.query(
    `INSERT INTO telemetry
       (device_eui, device_name, application_id, temperature, humidity, battery_level,
        rssi, snr, fcnt, payload, timestamp)
     VALUES ${placeholders}`,
    values
  )
}

export interface TelemetryQuery {
  deviceEui?: string
  from?: string
  to?: string
  limit: number
  offset: number
}

export async function queryTelemetry(
  q: TelemetryQuery
): Promise<{ rows: TelemetryRow[]; total: number }> {
  const conditions: string[] = []
  const params: unknown[] = []
  if (q.deviceEui) {
    params.push(q.deviceEui)
    conditions.push(`device_eui = $${params.length}`)
  }
  if (q.from) {
    params.push(q.from)
    conditions.push(`timestamp >= $${params.length}`)
  }
  if (q.to) {
    params.push(q.to)
    conditions.push(`timestamp <= $${params.length}`)
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

  const countResult = await pool.query<{ count: string }>(
    `SELECT COUNT(*)::text AS count FROM telemetry ${where}`,
    params
  )

  const limitIdx = params.length + 1
  const offsetIdx = params.length + 2
  params.push(q.limit, q.offset)

  const result = await pool.query<TelemetryRow>(
    `SELECT id, device_eui, device_name, application_id, temperature, humidity, battery_level,
            rssi, snr, fcnt, payload, timestamp
     FROM telemetry
     ${where}
     ORDER BY timestamp DESC
     LIMIT $${limitIdx} OFFSET $${offsetIdx}`,
    params
  )
  return { rows: result.rows, total: Number(countResult.rows[0]?.count ?? 0) }
}
