import { Pool } from 'pg'
import { env } from '../config/env'

export const pool = new Pool({
  connectionString: env.DATABASE_URL,
  max: env.DB_POOL_MAX,
  connectionTimeoutMillis: 5000,
  idleTimeoutMillis: 30000,
})

export async function waitForDb(retries = 10, delayMs = 3000): Promise<void> {
  for (let i = 1; i <= retries; i++) {
    try {
      await pool.query('SELECT 1')
      return
    } catch (err) {
      if (i === retries) throw err
      console.error(`[db] Conexão falhou (tentativa ${i}/${retries}), tentando novamente em ${delayMs}ms`)
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
  }
}
