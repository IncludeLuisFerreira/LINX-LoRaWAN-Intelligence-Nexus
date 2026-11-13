import { useEffect, type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { isTokenExpired } from '../utils/jwt';

interface AuthGuardProps {
  children: ReactNode;
}

/**
 * Protege rotas autenticadas: sem token ou com token expirado, redireciona
 * para /login. A expiração é verificada decodificando o `exp` do JWT.
 */
export function AuthGuard({ children }: AuthGuardProps) {
  const { accessToken, logout } = useAuth();
  const expired = !accessToken || isTokenExpired(accessToken);

  useEffect(() => {
    if (accessToken && expired) {
      logout();
    }
  }, [accessToken, expired, logout]);

  if (expired) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
