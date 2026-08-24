import { env } from '../config/env'
import { logger } from '../utils/logger'
import { sendTelegramAlert } from './telegramNotifier'
import { sendEmailAlert } from './emailNotifier'
import type { AlertEvent, AlertSender } from '../types'

export function createAlertSender(): AlertSender {
  const channels: Array<(event: AlertEvent) => Promise<void>> = []

  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    channels.push((event) => sendTelegramAlert(env.TELEGRAM_BOT_TOKEN!, env.TELEGRAM_CHAT_ID!, event))
    logger.info('[alerts] Canal Telegram ativo')
  }
  if (env.SMTP_HOST && env.ALERT_EMAIL_FROM && env.ALERT_EMAIL_TO) {
    channels.push(sendEmailAlert)
    logger.info('[alerts] Canal E-mail ativo')
  }
  if (channels.length === 0) {
    logger.warn('[alerts] Nenhum canal configurado — alertas apenas registrados no banco')
  }

  return {
    async send(event: AlertEvent): Promise<void> {
      await Promise.allSettled(channels.map((channel) => channel(event)))
    },
  }
}
