import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { pool } from './pool'
import { logger } from '../utils/logger'

export async function migrate(): Promise<void> {
  const initPath = path.join(__dirname, 'init.sql')
  const sql = await readFile(initPath, 'utf8')
  await pool.query(sql)
  logger.info('[db] Schema verificado (init.sql aplicado)')
}
