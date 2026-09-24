import { describe, expect, it } from 'vitest';
import { getErrorMessage } from './api';

function axiosErrorWithData(data: unknown, message = 'Request failed with status code 404') {
  return Object.assign(new Error(message), {
    isAxiosError: true,
    response: { data },
  });
}

describe('getErrorMessage', () => {
  it('returns the FastAPI detail field from an axios error response', () => {
    const error = axiosErrorWithData({ detail: 'Tenant not found!' });

    expect(getErrorMessage(error)).toBe('Tenant not found!');
  });

  it('falls back to the generic message when the response has no detail', () => {
    const error = axiosErrorWithData({}, 'Request failed with status code 500');

    expect(getErrorMessage(error)).toBe('Request failed with status code 500');
  });

  it('prefers detail over message when both are present', () => {
    const error = axiosErrorWithData(
      { detail: 'Application not found!', message: 'generic' },
      'Request failed with status code 404',
    );

    expect(getErrorMessage(error)).toBe('Application not found!');
  });

  it('supports legacy message field for backward compatibility', () => {
    const error = axiosErrorWithData({ message: 'legacy error' });

    expect(getErrorMessage(error)).toBe('legacy error');
  });

  it('returns the message of a plain Error', () => {
    expect(getErrorMessage(new Error('boom'))).toBe('boom');
  });

  it('returns the fallback for unknown values', () => {
    expect(getErrorMessage('nope')).toBe('Ocorreu um erro inesperado.');

    expect(getErrorMessage(null, 'custom')).toBe('custom');
  });
});
