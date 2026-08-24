import { Router } from 'express'
import { queryTelemetry } from '../repositories/telemetryRepository'

export const telemetryRouter = Router()

telemetryRouter.get('/', async (req, res, next) => {
  try {
    const limit = Math.min(Math.max(Number(req.query.limit) || 50, 1), 500)
    const offset = Math.max(Number(req.query.offset) || 0, 0)
    const deviceEui = typeof req.query.device_eui === 'string' ? req.query.device_eui : undefined
    const from = typeof req.query.from === 'string' ? req.query.from : undefined
    const to = typeof req.query.to === 'string' ? req.query.to : undefined
    const { rows, total } = await queryTelemetry({ deviceEui, from, to, limit, offset })
    res.json({ rows, total, limit, offset })
  } catch (err) {
    next(err)
  }
})
