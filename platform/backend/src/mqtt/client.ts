import mqtt, { type MqttClient } from 'mqtt'
import { env } from '../config/env'
import { logger } from '../utils/logger'

export function connectMqtt(onMessage: (topic: string, payload: string) => void): MqttClient {
  const client = mqtt.connect(env.MQTT_URL, {
    username: env.MQTT_USERNAME || undefined,
    password: env.MQTT_PASSWORD || undefined,
    reconnectPeriod: 3000,
    connectTimeout: 10000,
  })

  client.on('connect', () => {
    logger.info(`[mqtt] Conectado a ${env.MQTT_URL}`)
    client.subscribe(env.MQTT_TOPIC, (err) => {
      if (err) logger.error(`[mqtt] Falha ao subscrever ${env.MQTT_TOPIC}`, err)
      else logger.info(`[mqtt] Assinando tópico ${env.MQTT_TOPIC}`)
    })
  })
  client.on('reconnect', () => logger.info('[mqtt] Reconectando...'))
  client.on('offline', () => logger.warn('[mqtt] Offline'))
  client.on('error', (err) => logger.error('[mqtt] Erro', err))
  client.on('message', (topic, payload) => onMessage(topic, payload.toString()))

  return client
}
