import type { MetricValue, Reading } from '../types'

const METRIC_ALIASES: Record<string, string> = {
  volt_bateria: 'battery_level',
  volt_battery: 'battery_level',
  battery: 'battery_level',
}

function toNumber(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v)
  return undefined
}

function parseTimestamp(payload: Record<string, unknown>): string {
  const time = payload.time
  const nsTime = payload.nsTime
  if (typeof time === 'string') return time
  if (typeof nsTime === 'string') return nsTime
  return new Date().toISOString()
}

/**
 * Parse defensivo do payload JSON v4 (ChirpStack) publicado no tópico de uplink.
 * Retorna null para payloads malformados — nunca lança exceção.
 */
export function parseUplink(rawPayload: string): Reading | null {
  let payload: Record<string, any>
  try {
    payload = JSON.parse(rawPayload)
  } catch {
    return null
  }
  if (!payload || typeof payload !== 'object') return null

  const deviceInfo = payload.deviceInfo
  const deviceEui = deviceInfo?.deviceEui
  if (typeof deviceEui !== 'string' || deviceEui === '') return null

  const metrics: MetricValue = {}
  const obj = payload.object
  if (obj && typeof obj === 'object') {
    for (const [key, value] of Object.entries(obj)) {
      const num = toNumber(value)
      if (num === undefined) continue
      const normalizedKey = METRIC_ALIASES[key] ?? key
      metrics[normalizedKey] = num
    }
  }

  const rx = Array.isArray(payload.rxInfo) && payload.rxInfo.length > 0 ? payload.rxInfo[0] : {}

  return {
    deviceEui,
    deviceName: typeof deviceInfo?.deviceName === 'string' ? deviceInfo.deviceName : deviceEui,
    applicationId: typeof deviceInfo?.applicationId === 'string' ? deviceInfo.applicationId : '',
    fCnt: toNumber(payload.fCnt),
    rssi: toNumber(rx.rssi),
    snr: toNumber(rx.snr),
    metrics,
    timestamp: parseTimestamp(payload),
    raw: payload,
  }
}
