import { pool } from '../db/pool'

export interface AlertRow {
  id: number
  device_eui: string
  metric: string
  value: number
  threshold: number
  channel: string
  sent_at: string
  cooldown_until: string
}

export async function canAlert(deviceEui: string, metric: string): Promise<boolean> {
  const result = await pool.query<{ can: boolean }>(
    `SELECT NOT EXISTS (
       SELECT 1 FROM alerts
       WHERE device_eui = $1 AND metric = $2 AND cooldown_until > NOW()
     ) AS can`,
    [deviceEui, metric]
  )
  return result.rows[0]?.can ?? true
}

export async function registerAlert(
  deviceEui: string,
  metric: string,
  value: number,
  threshold: number,
  channel: string,
  cooldownMinutes: number
): Promise<void> {
  await pool.query(
    `INSERT INTO alerts (device_eui, metric, value, threshold, channel, cooldown_until)
     VALUES ($1, $2, $3, $4, $5, NOW() + make_interval(mins => $6))`,
    [deviceEui, metric, value, threshold, channel, cooldownMinutes]
  )
}

export async function listAlerts(
  limit: number,
  offset: number
): Promise<{ rows: AlertRow[]; total: number }> {
  const count = await pool.query<{ count: string }>('SELECT COUNT(*)::text AS count FROM alerts')
  const result = await pool.query<AlertRow>(
    `SELECT id, device_eui, metric, value, threshold, channel, sent_at, cooldown_until
     FROM alerts
     ORDER BY sent_at DESC
     LIMIT $1 OFFSET $2`,
    [limit, offset]
  )
  return { rows: result.rows, total: Number(count.rows[0]?.count ?? 0) }
}
