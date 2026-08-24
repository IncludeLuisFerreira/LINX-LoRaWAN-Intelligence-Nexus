import http from 'node:http'
import express from 'express'
import cors from 'cors'
import { Server } from 'socket.io'
import { env } from './config/env'
import { logger } from './utils/logger'
import { waitForDb } from './db/pool'
import { migrate } from './db/migrate'
import { connectMqtt } from './mqtt/client'
import { parseUplink } from './mqtt/parser'
import { PersistService } from './services/persistService'
import { setupLiveService } from './services/liveService'
import { ThresholdEngine } from './services/thresholdEngine'
import { createAlertSender } from './alerts'
import { healthRouter } from './routes/health'
import { telemetryRouter } from './routes/telemetry'
import { devicesRouter } from './routes/devices'
import { alertsRouter } from './routes/alerts'

async function main(): Promise<void> {
  await waitForDb()
  await migrate()

  const app = express()
  app.use(express.json())
  if (env.CORS_ORIGIN) app.use(cors({ origin: env.CORS_ORIGIN }))

  app.use('/api/health', healthRouter)
  app.use('/api/telemetry', telemetryRouter)
  app.use('/api/devices', devicesRouter)
  app.use('/api/alerts', alertsRouter)

  const server = http.createServer(app)
  const io = new Server(server, {
    cors: { origin: env.CORS_ORIGIN ?? true },
  })
  const live = setupLiveService(io)

  const persist = new PersistService()
  persist.start()

  const sender = createAlertSender()
  const engine = new ThresholdEngine(sender)

  connectMqtt((topic, payload) => {
    const reading = parseUplink(payload)
    if (!reading) {
      logger.warn(`[mqtt] Payload inválido descartado (tópico ${topic})`)
      return
    }
    persist.enqueue(reading)
    live.emitReading(reading)
    void engine.process(reading).catch((err) => logger.error('[alerts] Falha ao processar regras', err))
  })

  server.listen(env.PORT, () => {
    logger.info(`[http] Dashboard backend em http://0.0.0.0:${env.PORT}`)
  })
}

main().catch((err) => {
  logger.error('[fatal] Falha ao iniciar backend', err)
  process.exit(1)
})
