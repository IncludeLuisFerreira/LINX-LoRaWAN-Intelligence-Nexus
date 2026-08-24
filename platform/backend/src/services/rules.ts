import type { ThresholdOperator } from '../types'

export interface ThresholdRule {
  metric: string
  operator: ThresholdOperator
  value: number
}

const RULE_PATTERN = /^([A-Za-z0-9_]+):(>=|<=|>|<):(-?\d+(?:\.\d+)?)$/

export function parseRules(raw: string): ThresholdRule[] {
  const rules: ThresholdRule[] = []
  for (const part of raw.split(';')) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const match = RULE_PATTERN.exec(trimmed)
    if (!match) {
      throw new Error(`Regra inválida: "${trimmed}" (esperado metrica:operador:valor, ex.: ldr_value:>:500)`)
    }
    rules.push({ metric: match[1], operator: match[2] as ThresholdOperator, value: Number(match[3]) })
  }
  return rules
}

export function evaluateRule(rule: ThresholdRule, value: number): boolean {
  switch (rule.operator) {
    case '>':
      return value > rule.value
    case '<':
      return value < rule.value
    case '>=':
      return value >= rule.value
    case '<=':
      return value <= rule.value
  }
}
