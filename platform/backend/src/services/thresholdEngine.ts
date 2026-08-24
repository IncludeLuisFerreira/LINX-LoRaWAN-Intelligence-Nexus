import { canAlert, registerAlert } from '../repositories/alertRepository'
import { env } from '../config/env'
import { parseRules, evaluateRule, type ThresholdRule } from './rules'
import { logger } from '../utils/logger'
import type { AlertEvent, AlertSender, Reading } from '../types'

export class ThresholdEngine {
  private rules: ThresholdRule[] = []

  constructor(
    private readonly sender: AlertSender,
    rulesRaw = env.THRESHOLD_RULES
  ) {
    this.rules = parseRules(rulesRaw)
  }

  async process(reading: Reading): Promise<void> {
    if (this.rules.length === 0) return
    for (const rule of this.rules) {
      const value = reading.metrics[rule.metric]
      if (value === undefined) continue
      if (!evaluateRule(rule, value)) continue
      if (!(await canAlert(reading.deviceEui, rule.metric))) continue
      await registerAlert(
        reading.deviceEui,
        rule.metric,
        value,
        rule.value,
        'all',
        env.ALERT_COOLDOWN_MINUTES
      )
      const event: AlertEvent = {
        deviceEui: reading.deviceEui,
        deviceName: reading.deviceName,
        metric: rule.metric,
        value,
        threshold: rule.value,
        operator: rule.operator,
        timestamp: reading.timestamp,
      }
      await this.sender.send(event)
      logger.warn(
        `[alerts] ${reading.deviceName} (${reading.deviceEui}): ${rule.metric} = ${value} ${rule.operator} ${rule.value}`
      )
    }
  }
}
