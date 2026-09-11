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
  // Simula o delay de uma requisição HTTP
  await new Promise((resolve) => setTimeout(resolve, 800));

  // Mock de erro quando a senha for "erro"
  if (password === 'erro') {
    throw new Error('Credenciais inválidas.');
  }

  const response: AuthResponse = {
    accessToken: 'mock-token',
    refreshToken: 'mock-refresh',
    user: { email },
  };

  // Armazena no localStorage para manter a sessão mockada
  localStorage.setItem('accessToken', response.accessToken);
  localStorage.setItem('user', JSON.stringify(response.user));

  return response;
}
