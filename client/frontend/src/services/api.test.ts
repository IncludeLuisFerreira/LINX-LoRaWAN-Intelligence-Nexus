import { afterEach, describe, expect, it } from 'vitest';
import {
  api,
  clearAccessToken,
  getAccessToken,
  getErrorMessage,
  setAccessToken,
} from './api';

// O token vive no módulo api.ts; sem este reset ele vazaria entre os casos.
afterEach(() => {
  clearAccessToken();
});

function axiosErrorWithData(
  data: unknown,
  message = 'Request failed with status code 404',
) {
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

  it('joins FastAPI 422 detail array messages', () => {
    const error = axiosErrorWithData({
      detail: [
        { msg: 'description must not be empty', loc: ['body', 'description'] },
        { msg: 'name too short', loc: ['body', 'name'] },
      ],
    });

    expect(getErrorMessage(error)).toBe(
      'description must not be empty; name too short',
    );
  });

  it('returns the fallback for unknown values', () => {
    expect(getErrorMessage('nope')).toBe('Ocorreu um erro inesperado.');

    expect(getErrorMessage(null, 'custom')).toBe('custom');
  });
});

describe('api auth configuration', () => {
  it('keeps the access token only in memory', () => {
    setAccessToken('memory-jwt');
    expect(getAccessToken()).toBe('memory-jwt');

    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });

  it('sends credentials so the httpOnly refresh cookie is stored', () => {
    expect(api.defaults.withCredentials).toBe(true);
  });
});
