import { api } from './api';

export const RULE_OPERATORS = ['>', '<', '==', '!='] as const;
export const RULE_ACTION_TYPES = ['downlink', 'telegram', 'email'] as const;

export type RuleOperator = (typeof RULE_OPERATORS)[number];
export type RuleActionType = (typeof RULE_ACTION_TYPES)[number];

export interface Rule {
  id: string;
  sensor_field: string;
  operator: RuleOperator;
  threshold: number;
  action_type: RuleActionType;
}

export type CreateRuleInput = Omit<Rule, 'id'>;

export const ruleService = {
  list: async (): Promise<Rule[]> => {
    const response = await api.get<Rule[]>('/rules');
    return response.data;
  },

  create: async (payload: CreateRuleInput): Promise<Rule> => {
    const response = await api.post<Rule>('/rules', payload);
    return response.data;
  },
};
