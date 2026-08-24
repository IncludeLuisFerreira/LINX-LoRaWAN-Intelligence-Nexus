import { Router } from 'express'
import { listDevices } from '../repositories/deviceRepository'
import { env } from '../config/env'

export const devicesRouter = Router()

devicesRouter.get('/', async (_req, res, next) => {
  try {
    const devices = await listDevices(env.OFFLINE_THRESHOLD_MINUTES)
    res.json({ devices })
  } catch (err) {
    next(err)
  }
})
