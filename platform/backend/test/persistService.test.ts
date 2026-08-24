import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { Reading } from '../src/types'

const mocks = vi.hoisted(() => ({
  insertTelemetryBatch: vi.fn(),
  upsertDevices: vi.fn(),
  waitForDb: vi.fn(),
}))

vi.mock('../src/repositories/telemetryRepository', () => ({
  insertTelemetryBatch: mocks.insertTelemetryBatch,
}))
vi.mock('../src/repositories/deviceRepository', () => ({
  upsertDevices: mocks.upsertDevices,
}))
vi.mock('../src/db/pool', () => ({
  waitForDb: mocks.waitForDb,
}))

import { PersistService } from '../src/services/persistService'

const makeReading = (i: number): Reading => ({
  deviceEui: `eui-${i}`,
  deviceName: `dev-${i}`,
  applicationId: 'app',
  metrics: { ldr_value: i },
  timestamp: new Date().toISOString(),
  raw: {},
})

describe('PersistService', () => {
  let service: PersistService

  beforeEach(() => {
    vi.useFakeTimers()
    mocks.insertTelemetryBatch.mockReset()
    mocks.upsertDevices.mockReset()
    mocks.waitForDb.mockResolvedValue(undefined)
    service = new PersistService()
  })

  afterEach(() => {
    service.stop()
    vi.useRealTimers()
  })

  it('grava lote em batch e limpa a fila', async () => {
    service.enqueue(makeReading(1))
    service.enqueue(makeReading(2))
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(1)
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledWith([expect.anything(), expect.anything()])
    expect(mocks.upsertDevices).toHaveBeenCalledWith([expect.anything(), expect.anything()])
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(1)
  })

  it('reenfileira o lote quando a gravação falha', async () => {
    mocks.insertTelemetryBatch.mockRejectedValueOnce(new Error('db down'))
    service.enqueue(makeReading(1))
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(1)
    await service.flush()
    expect(mocks.insertTelemetryBatch).toHaveBeenCalledTimes(2)
  })

  it('descartar a leitura mais antiga quando a fila estoura', () => {
    const bounded = new PersistService(5)
    for (let i = 0; i < 7; i++) bounded.enqueue(makeReading(i))
    expect(bounded.size()).toBe(5)
    const queue = (bounded as unknown as { queue: Reading[] }).queue
    expect(queue[0].deviceEui).toBe('eui-2')
    expect(queue[4].deviceEui).toBe('eui-6')
  })
})
