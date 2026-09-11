import { api } from './api';

export interface User {
  email: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: User;
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  // Simulação mockada enquanto a API real não está pronta
  await new Promise((resolve) => setTimeout(resolve, 800));

  if (password === 'erro') {
    throw new Error('Credenciais inválidas.');
  }

  const response: AuthResponse = {
    accessToken: 'mock-token-123456',
    refreshToken: 'mock-refresh-token',
    user: { email },
  };

  localStorage.setItem('accessToken', response.accessToken);
  localStorage.setItem('user', JSON.stringify(response.user));

  return response;
}

// Exemplo de chamada que usará a instância da API
export async function getOrgs() {
  const response = await api.get('/orgs');
  return response.data;
}
