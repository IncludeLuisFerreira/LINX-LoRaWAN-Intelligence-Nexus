import { describe, it, expect } from 'vitest'
import { parseUplink } from '../src/mqtt/parser'

const VALID_PAYLOAD = JSON.stringify({
  deviceInfo: {
    deviceEui: '0011223344556677',
    deviceName: 'esp32-ldr-01',
    applicationId: 'app-01',
  },
  fCnt: 42,
  rxInfo: [{ rssi: -72, snr: 8.5 }],
  time: '2026-07-30T12:00:00Z',
  object: { ldr_value: 412, volt_bateria: 3.9 },
})

describe('parseUplink', () => {
  it('parseia payload v4 válido e normaliza métricas', () => {
    const r = parseUplink(VALID_PAYLOAD)
    expect(r).not.toBeNull()
    expect(r!.deviceEui).toBe('0011223344556677')
    expect(r!.deviceName).toBe('esp32-ldr-01')
    expect(r!.applicationId).toBe('app-01')
    expect(r!.fCnt).toBe(42)
    expect(r!.rssi).toBe(-72)
    expect(r!.snr).toBe(8.5)
    expect(r!.metrics.ldr_value).toBe(412)
    expect(r!.metrics.battery_level).toBe(3.9)
    expect(r!.timestamp).toBe('2026-07-30T12:00:00Z')
  })

  it('aceita valores numéricos em string', () => {
    const r = parseUplink(
      JSON.stringify({
        deviceInfo: { deviceEui: 'aa' },
        object: { ldr_value: '300' },
      })
    )
    expect(r!.metrics.ldr_value).toBe(300)
  })

  it('rejeita JSON inválido com null', () => {
    expect(parseUplink('{not json')).toBeNull()
  })

  it('rejeita payload sem deviceEui', () => {
    expect(parseUplink(JSON.stringify({ fCnt: 1 }))).toBeNull()
  })

  it('ignora métricas não numéricas', () => {
    const r = parseUplink(
      JSON.stringify({
        deviceInfo: { deviceEui: 'aa' },
        object: { nome: 'sensor', ldr_value: 10 },
      })
    )
    expect(r!.metrics.nome).toBeUndefined()
    expect(r!.metrics.ldr_value).toBe(10)
  })
})
