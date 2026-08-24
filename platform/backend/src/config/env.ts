import 'dotenv/config'
import { z } from 'zod'

const EnvSchema = z.object({
  PORT: z.coerce.number().default(4000),
  MQTT_URL: z.string().default('mqtt://host.docker.internal:1883'),
  MQTT_TOPIC: z.string().default('application/+/device/+/event/up'),
  MQTT_USERNAME: z.string().optional(),
  MQTT_PASSWORD: z.string().optional(),
  DATABASE_URL: z
    .string()
    .default('postgres://dashboard:dashboard@postgres:5432/dashboard'),
  DB_POOL_MAX: z.coerce.number().default(10),
  PERSIST_FLUSH_MS: z.coerce.number().default(1000),
  PERSIST_BATCH_SIZE: z.coerce.number().default(200),
  QUEUE_MAX_SIZE: z.coerce.number().default(5000),
  OFFLINE_THRESHOLD_MINUTES: z.coerce.number().default(5),
  THRESHOLD_RULES: z.string().default(''),
  ALERT_COOLDOWN_MINUTES: z.coerce.number().default(5),
  TELEGRAM_BOT_TOKEN: z.string().optional(),
  TELEGRAM_CHAT_ID: z.string().optional(),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z.coerce.number().optional(),
  SMTP_SECURE: z.coerce.boolean().default(false),
  SMTP_USER: z.string().optional(),
  SMTP_PASS: z.string().optional(),
  ALERT_EMAIL_FROM: z.string().optional(),
  ALERT_EMAIL_TO: z.string().optional(),
  CORS_ORIGIN: z.string().optional(),
})

const parsed = EnvSchema.safeParse(process.env)

if (!parsed.success) {
  console.error('[env] Configuração inválida:', JSON.stringify(parsed.error.flatten().fieldErrors, null, 2))
  process.exit(1)
}

export const env = parsed.data
