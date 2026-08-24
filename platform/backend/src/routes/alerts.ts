import { Router } from 'express'
import { listAlerts } from '../repositories/alertRepository'

export const alertsRouter = Router()

alertsRouter.get('/', async (req, res, next) => {
  try {
    const limit = Math.min(Math.max(Number(req.query.limit) || 20, 1), 200)
    const offset = Math.max(Number(req.query.offset) || 0, 0)
    const { rows, total } = await listAlerts(limit, offset)
    res.json({ rows, total, limit, offset })
  } catch (err) {
    next(err)
  }
})
