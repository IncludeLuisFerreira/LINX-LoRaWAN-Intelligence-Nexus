import { describe, expect, it } from 'vitest';
import { cleanOptionalDescription } from './form';

describe('cleanOptionalDescription', () => {
  it('omits an empty description', () => {
    expect(
      cleanOptionalDescription({ name: 'ACME', description: '' }),
    ).toEqual({ name: 'ACME' });
  });

  it('omits a whitespace-only description', () => {
    expect(
      cleanOptionalDescription({ name: 'ACME', description: '   ' }),
    ).toEqual({ name: 'ACME' });
  });

  it('trims and keeps a non-empty description', () => {
    expect(
      cleanOptionalDescription({ name: 'ACME', description: '  ops  ' }),
    ).toEqual({ name: 'ACME', description: 'ops' });
  });
});
