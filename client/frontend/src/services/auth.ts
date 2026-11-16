import { api } from './api';

export interface LoginResponse {
  access_token: string;
  token_type?: string;
  expires_in?: number;
}

/**
 * Autentica o usuário via POST /auth/login.
 *
 * O backend devolve o `access_token` no corpo (mantido apenas em memória pelo
 * AuthContext) e define o `refresh_token` em um cookie httpOnly. O cookie é
 * gerenciado pelo navegador; JavaScript não deve (nem consegue) lê-lo.
 */
export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login', {
    email,
    password,
  });

  return data;
}
