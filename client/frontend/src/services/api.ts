import axios from 'axios';

// O access token vive apenas em memória (nunca em localStorage/sessionStorage),
// reduzindo a superfície de ataque de XSS. O refresh token fica em cookie
// httpOnly controlado pelo backend.
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearAccessToken() {
  accessToken = null;
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
  // Necessário para o navegador enviar/receber o cookie httpOnly de refresh
  // em requisições cross-origin (ex.: Vite em :5173 e API em :8000).
  withCredentials: true,
});

// Interceptor de Requisição: Injeta o token Bearer em memória no Header
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// Interceptor de Resposta: Trata o erro 401 (Não Autorizado)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Limpa o access token expirado da memória
      accessToken = null;

      // Redireciona para o login caso não esteja na tela de login
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

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
