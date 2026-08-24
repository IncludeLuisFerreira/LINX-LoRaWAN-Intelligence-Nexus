import type { AlertsResponse, DevicesResponse, TelemetryResponse } from '../types'

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export interface TelemetryParams {
  deviceEui?: string
  from?: string
  to?: string
  limit: number
  offset: number
}

export const api = {
  telemetry(params: TelemetryParams): Promise<TelemetryResponse> {
    const q = new URLSearchParams()
    if (params.deviceEui) q.set('device_eui', params.deviceEui)
    if (params.from) q.set('from', params.from)
    if (params.to) q.set('to', params.to)
    q.set('limit', String(params.limit))
    q.set('offset', String(params.offset))
    return get<TelemetryResponse>(`/api/telemetry?${q.toString()}`)
  },
  devices(): Promise<DevicesResponse> {
    return get<DevicesResponse>('/api/devices')
  },
  alerts(limit = 20): Promise<AlertsResponse> {
    return get<AlertsResponse>(`/api/alerts?limit=${limit}`)
  },
}
