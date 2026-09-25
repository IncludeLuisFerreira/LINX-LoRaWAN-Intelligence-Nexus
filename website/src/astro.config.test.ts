import { describe, expect, it } from 'vitest';
import config from '../astro.config.mjs';

describe('astro.config', () => {
  it('mantém a proteção de origem (CSRF) habilitada', () => {
    expect(config.security?.checkOrigin).toBe(true);
  });
});
