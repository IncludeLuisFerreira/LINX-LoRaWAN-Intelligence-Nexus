import type { AlertEvent } from '../types'

export async function sendTelegramAlert(
  token: string,
  chatId: string,
  event: AlertEvent
): Promise<void> {
  const text = [
    '🚨 ALERTA LoRaWAN',
    `Device: ${event.deviceName} (${event.deviceEui})`,
    `Métrica: ${event.metric}`,
    `Valor: ${event.value} ${event.operator} ${event.threshold}`,
    `Horário: ${event.timestamp}`,
  ].join('\n')

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  })
  if (!res.ok) {
    throw new Error(`Telegram HTTP ${res.status}: ${await res.text()}`)
  }
}
