import { describe, it, expect } from 'vitest'
import { parseRules, evaluateRule } from '../src/services/rules'

describe('parseRules', () => {
  it('parseia múltiplas regras no formato metrica:operador:valor', () => {
    const rules = parseRules('ldr_value:>:500;temperature:>:35;battery_level:<:3.2')
    expect(rules).toEqual([
      { metric: 'ldr_value', operator: '>', value: 500 },
      { metric: 'temperature', operator: '>', value: 35 },
      { metric: 'battery_level', operator: '<', value: 3.2 },
    ])
  })

  it('ignora partes vazias e espaços', () => {
    const rules = parseRules('  ldr_value:>:100 ;  ; temperature:>=:40  ')
    expect(rules).toHaveLength(2)
    expect(rules[1].operator).toBe('>=')
  })

  it('lança erro para regra malformada', () => {
    expect(() => parseRules('ldr_value:>')).toThrow(/Regra inválida/)
  })

  it('retorna lista vazia para string vazia', () => {
    expect(parseRules('')).toEqual([])
  })
})

describe('evaluateRule', () => {
  const cases: Array<[string, number, number, boolean]> = [
    ['>', 501, 500, true],
    ['>', 500, 500, false],
    ['>=', 500, 500, true],
    ['<', 3.1, 3.2, true],
    ['<', 3.3, 3.2, false],
    ['<=', 3.2, 3.2, true],
  ]
  it.each(cases)('operador %s: valor %d vs limite %d → %s', (op, value, threshold, expected) => {
    expect(evaluateRule({ metric: 'm', operator: op as never, value: threshold }, value)).toBe(expected)
  })
})
