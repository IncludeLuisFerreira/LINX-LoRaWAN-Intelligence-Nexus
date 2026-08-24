import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Reading } from '../src/types'

const mocks = vi.hoisted(() => ({
  canAlert: vi.fn(),
  registerAlert: vi.fn(),
}))

vi.mock('../src/repositories/alertRepository', () => ({
  canAlert: mocks.canAlert,
  registerAlert: mocks.registerAlert,
}))

import { ThresholdEngine } from '../src/services/thresholdEngine'

const RULES = 'ldr_value:>:500;battery_level:<:3.2'

const makeReading = (metrics: Record<string, number>): Reading => ({
  deviceEui: 'eui-1',
  deviceName: 'esp-1',
  applicationId: 'app',
  metrics,
  timestamp: '2026-07-30T12:00:00Z',
  raw: {},
})

describe('ThresholdEngine', () => {
  let sender: { send: ReturnType<typeof vi.fn> }

  beforeEach(() => {
    sender = { send: vi.fn().mockResolvedValue(undefined) }
    mocks.canAlert.mockReset()
    mocks.registerAlert.mockReset()
    mocks.canAlert.mockResolvedValue(true)
    mocks.registerAlert.mockResolvedValue(undefined)
  })

  it('dispara alerta quando a métrica ultrapassa o limite', async () => {
    const engine = new ThresholdEngine(sender, RULES)
    await engine.process(makeReading({ ldr_value: 600, battery_level: 3.9 }))
    expect(sender.send).toHaveBeenCalledTimes(1)
    expect(sender.send).toHaveBeenCalledWith(
      expect.objectContaining({ metric: 'ldr_value', value: 600, threshold: 500 })
    )
    expect(mocks.registerAlert).toHaveBeenCalledWith(
      'eui-1', 'ldr_value', 600, 500, expect.any(String), 5
    )
  })

  it('não dispara quando nenhuma regra é violada', async () => {
    const engine = new ThresholdEngine(sender, RULES)
    await engine.process(makeReading({ ldr_value: 100, battery_level: 3.9 }))
    expect(sender.send).not.toHaveBeenCalled()
  })

  it('respeita o cooldown (canAlert falso → sem envio)', async () => {
    mocks.canAlert.mockResolvedValue(false)
    const engine = new ThresholdEngine(sender, RULES)
    await engine.process(makeReading({ ldr_value: 900 }))
    expect(sender.send).not.toHaveBeenCalled()
    expect(mocks.registerAlert).not.toHaveBeenCalled()
  })
})
