export interface MetricValue {
  [metric: string]: number
}

export interface Reading {
  deviceEui: string
  deviceName: string
  applicationId: string
  fCnt?: number
  rssi?: number
  snr?: number
  metrics: MetricValue
  timestamp: string
  raw: unknown
}

export type ThresholdOperator = '>' | '<' | '>=' | '<='

export interface AlertEvent {
  deviceEui: string
  deviceName: string
  metric: string
  value: number
  threshold: number
  operator: ThresholdOperator
  timestamp: string
}

export interface AlertSender {
  send(event: AlertEvent): Promise<void>
}
