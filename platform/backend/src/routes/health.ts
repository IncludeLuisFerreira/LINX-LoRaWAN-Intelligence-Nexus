import { Router } from 'express'
import { pool } from '../db/pool'

export const healthRouter = Router()

healthRouter.get('/', async (_req, res) => {
  let dbOk = false
  try {
    await pool.query('SELECT 1')
    dbOk = true
  } catch {
    dbOk = false
  }
  res.json({ status: 'ok', db: dbOk ? 'up' : 'down', uptime: process.uptime() })
})
