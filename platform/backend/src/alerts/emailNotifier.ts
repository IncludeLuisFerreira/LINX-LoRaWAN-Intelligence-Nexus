import nodemailer from 'nodemailer'
import { env } from '../config/env'
import type { AlertEvent } from '../types'

export async function sendEmailAlert(event: AlertEvent): Promise<void> {
  const transporter = nodemailer.createTransport({
    host: env.SMTP_HOST,
    port: env.SMTP_PORT,
    secure: env.SMTP_SECURE,
    auth:
      env.SMTP_USER && env.SMTP_PASS
        ? { user: env.SMTP_USER, pass: env.SMTP_PASS }
        : undefined,
  })

  await transporter.sendMail({
    from: env.ALERT_EMAIL_FROM,
    to: env.ALERT_EMAIL_TO,
    subject: `[LoRaWAN] Alerta: ${event.metric} ${event.operator} ${event.threshold}`,
    html: `
      <h2>🚨 Alerta LoRaWAN</h2>
      <table border="1" cellpadding="8" style="border-collapse: collapse">
        <tr><td><b>Device</b></td><td>${event.deviceName} (${event.deviceEui})</td></tr>
        <tr><td><b>Métrica</b></td><td>${event.metric}</td></tr>
        <tr><td><b>Valor</b></td><td>${event.value}</td></tr>
        <tr><td><b>Limite</b></td><td>${event.operator} ${event.threshold}</td></tr>
        <tr><td><b>Horário</b></td><td>${event.timestamp}</td></tr>
      </table>
    `,
  })
}
