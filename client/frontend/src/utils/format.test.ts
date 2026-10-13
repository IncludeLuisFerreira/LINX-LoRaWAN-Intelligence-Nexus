import { describe, expect, it } from 'vitest';
import { cn } from './cn';
import { formatDate } from './format';

describe('cn', () => {
  it('joins truthy class names', () => {
    expect(cn('a', false, undefined, 'b', null)).toBe('a b');
  });
});

describe('formatDate', () => {
  it('returns a dash for empty input', () => {
    expect(formatDate('')).toBe('—');
  });

  it('returns a dash for invalid input', () => {
    expect(formatDate('not-a-date')).toBe('—');
  });

  it('formats a valid ISO date', () => {
    expect(formatDate('2026-10-10T14:30:00Z')).toMatch(
      /\d{2}\/\d{2}\/\d{4}/,
    );
  });
});
