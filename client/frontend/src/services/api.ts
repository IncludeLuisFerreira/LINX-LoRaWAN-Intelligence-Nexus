import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
});

export function getErrorMessage(
  error: unknown,
  fallbackMessage = 'Ocorreu um erro inesperado.',
): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: unknown; message?: unknown }
      | undefined;
    if (typeof data?.detail === 'string' && data.detail) return data.detail;
    if (Array.isArray(data?.detail)) {
      const messages = data.detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : '',
        )
        .filter(Boolean);
      if (messages.length > 0) return messages.join('; ');
    }
    if (typeof data?.message === 'string' && data.message) return data.message;
    return error.message || fallbackMessage;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallbackMessage;
}
