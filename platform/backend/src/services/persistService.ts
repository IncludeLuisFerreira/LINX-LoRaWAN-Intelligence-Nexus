import { insertTelemetryBatch } from '../repositories/telemetryRepository'
import { upsertDevices } from '../repositories/deviceRepository'
import { waitForDb } from '../db/pool'
import { env } from '../config/env'
import { logger } from '../utils/logger'
import type { Reading } from '../types'

export class PersistService {
  private readonly queueMaxSize: number
  private queue: Reading[] = []
  private timer: NodeJS.Timeout | null = null
  private flushing = false

  constructor(queueMaxSize = env.QUEUE_MAX_SIZE) {
    this.queueMaxSize = queueMaxSize
  }

  start(): void {
    if (this.timer) return
    this.timer = setInterval(() => void this.flush(), env.PERSIST_FLUSH_MS)
    logger.info(`[persist] Fila iniciada (flush a cada ${env.PERSIST_FLUSH_MS}ms, batch de ${env.PERSIST_BATCH_SIZE})`)
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
  }

  enqueue(reading: Reading): void {
    if (this.queue.length >= this.queueMaxSize) {
      logger.warn('[persist] Fila cheia, descartando leitura mais antiga')
      this.queue.shift()
    }
    this.queue.push(reading)
  }

  size(): number {
    return this.queue.length
  }

  async flush(): Promise<void> {
    if (this.flushing || this.queue.length === 0) return
    this.flushing = true
    const batch = this.queue.splice(0, env.PERSIST_BATCH_SIZE)
    try {
      await waitForDb()
      await insertTelemetryBatch(batch)
      await upsertDevices(batch)
    } catch (err) {
      logger.error('[persist] Erro ao gravar lote, reenfileirando', err)
      this.queue.unshift(...batch)
    } finally {
      this.flushing = false
    }
  }
}
