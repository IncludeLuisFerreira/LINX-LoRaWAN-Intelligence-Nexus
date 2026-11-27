import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { api } from './api';
import { ruleService } from './rule';

vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mocked = api as unknown as Record<'get' | 'post', Mock>;

describe('ruleService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists rules with GET /rules', async () => {
    const rules = [
      {
        id: 'r1',
        sensor_field: 'temperatura',
        operator: '>',
        threshold: 40,
        action_type: 'downlink',
      },
    ];
    mocked.get.mockResolvedValue({ data: rules });

    const result = await ruleService.list();

    expect(mocked.get).toHaveBeenCalledWith('/rules');
    expect(result).toEqual(rules);
  });

  it('creates a rule with POST /rules', async () => {
    const payload = {
      sensor_field: 'temperatura',
      operator: '>' as const,
      threshold: 40,
      action_type: 'downlink' as const,
    };
    mocked.post.mockResolvedValue({ data: { id: 'r2', ...payload } });

    const result = await ruleService.create(payload);

    expect(mocked.post).toHaveBeenCalledWith('/rules', payload);
    expect(result).toEqual({ id: 'r2', ...payload });
  });
});
