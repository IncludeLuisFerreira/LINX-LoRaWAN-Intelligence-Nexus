import { describe, it, expect, beforeEach, vi } from 'vitest'

describe('env', () => {
  const originalEnv = process.env

  beforeEach(() => {
    vi.resetModules()
    process.env = { ...originalEnv }
  })

  it('aplica defaults quando variáveis não são informadas', async () => {
    for (const key of [
      'PORT', 'MQTT_URL', 'MQTT_TOPIC', 'DATABASE_URL', 'PERSIST_FLUSH_MS',
      'PERSIST_BATCH_SIZE', 'QUEUE_MAX_SIZE', 'OFFLINE_THRESHOLD_MINUTES',
      'ALERT_COOLDOWN_MINUTES',
    ]) {
      delete process.env[key]
    }
    const { env } = await import('../src/config/env')
    expect(env.PORT).toBe(4000)
    expect(env.MQTT_URL).toBe('mqtt://host.docker.internal:1883')
    expect(env.MQTT_TOPIC).toBe('application/+/device/+/event/up')
    expect(env.PERSIST_FLUSH_MS).toBe(1000)
    expect(env.PERSIST_BATCH_SIZE).toBe(200)
    expect(env.QUEUE_MAX_SIZE).toBe(5000)
    expect(env.OFFLINE_THRESHOLD_MINUTES).toBe(5)
    expect(env.ALERT_COOLDOWN_MINUTES).toBe(5)
  })

  it('faz coerção de tipos numéricos', async () => {
    process.env.PORT = '8080'
    process.env.PERSIST_FLUSH_MS = '250'
    const { env } = await import('../src/config/env')
    expect(env.PORT).toBe(8080)
    expect(env.PERSIST_FLUSH_MS).toBe(250)
  })
})
