export interface Reading {
  deviceEui: string
  deviceName: string
  applicationId: string
  fCnt?: number
  rssi?: number
  snr?: number
  metrics: Record<string, number>
  timestamp: string
}

export interface DeviceStatus {
  device_eui: string
  device_name: string
  application_id: string
  last_seen_at: string
  last_rssi: number | null
  last_snr: number | null
  created_at: string
  online: boolean
}

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

export interface TelemetryResponse {
  rows: TelemetryRow[]
  total: number
  limit: number
  offset: number
}

export interface DevicesResponse {
  devices: DeviceStatus[]
}

export interface AlertsResponse {
  rows: AlertRow[]
  total: number
  limit: number
  offset: number
}
