import { pool } from '../db/pool'
import type { Reading } from '../types'

export interface DeviceRow {
  device_eui: string
  device_name: string
  application_id: string
  last_seen_at: string
  last_rssi: number | null
  last_snr: number | null
  created_at: string
}

export interface DeviceStatusRow extends DeviceRow {
  online: boolean
}

const DEVICE_COLUMNS = 6

export async function upsertDevices(readings: Reading[]): Promise<void> {
  if (readings.length === 0) return
  const values: unknown[] = []
  const rows: unknown[][] = []
  for (const r of readings) {
    rows.push([r.deviceEui, r.deviceName, r.applicationId, r.timestamp, r.rssi ?? null, r.snr ?? null])
  }
  for (const row of rows) values.push(...row)
  const placeholders = rows
    .map((_, i) => {
      const base = i * DEVICE_COLUMNS
      const parts: string[] = []
      for (let c = 1; c <= DEVICE_COLUMNS; c++) parts.push(`$${base + c}`)
      return `(${parts.join(', ')})`
    })
    .join(', ')
  await pool.query(
    `INSERT INTO devices (device_eui, device_name, application_id, last_seen_at, last_rssi, last_snr)
     VALUES ${placeholders}
     ON CONFLICT (device_eui) DO UPDATE SET
       device_name = EXCLUDED.device_name,
       application_id = EXCLUDED.application_id,
       last_seen_at = EXCLUDED.last_seen_at,
       last_rssi = EXCLUDED.last_rssi,
       last_snr = EXCLUDED.last_snr`,
    values
  )
}

export async function listDevices(offlineThresholdMinutes: number): Promise<DeviceStatusRow[]> {
  const result = await pool.query<DeviceStatusRow>(
    `SELECT device_eui, device_name, application_id, last_seen_at, last_rssi, last_snr, created_at,
            (last_seen_at > NOW() - make_interval(mins => $1)) AS online
     FROM devices
     ORDER BY last_seen_at DESC`,
    [offlineThresholdMinutes]
  )
  return result.rows
}
