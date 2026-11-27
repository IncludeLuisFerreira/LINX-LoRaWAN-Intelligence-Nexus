import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { login as loginRequest, type LoginResponse } from '../services/auth';
import { clearAccessToken, setAccessToken } from '../services/api';
import { decodeToken, getPermissions } from '../utils/jwt';

interface AuthContextValue {
  accessToken: string | null;
  isAuthenticated: boolean;
  permissions: string[];
  /** `sub` do JWT — identifica o usuário autenticado (ex.: guard de auto-desativação). */
  userId: string | null;
  /** Claim `email` do JWT, quando presente. */
  email: string | null;
  login: (email: string, password: string) => Promise<LoginResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  // O access token é mantido somente em memória (estado do React + módulo api).
  // Recarregar a página encerra a sessão até um refresh futuro via cookie.
  const [accessToken, setToken] = useState<string | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    const session = await loginRequest(email, password);

    setAccessToken(session.access_token);
    setToken(session.access_token);

    return session;
  }, []);

  const logout = useCallback(() => {
    clearAccessToken();
    setToken(null);
  }, []);

  // As permissões vêm da claim `permissions` do access token (RBAC).
  const permissions = useMemo(
    () => (accessToken ? getPermissions(accessToken) : []),
    [accessToken],
  );

  // A identidade vem do JWT (claims `sub` e `email`), sem estado adicional.
  const identity = useMemo(() => {
    const payload = accessToken ? decodeToken(accessToken) : null;
    return {
      userId: typeof payload?.sub === 'string' ? payload.sub : null,
      email: typeof payload?.email === 'string' ? payload.email : null,
    };
  }, [accessToken]);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      isAuthenticated: Boolean(accessToken),
      permissions,
      ...identity,
      login,
      logout,
    }),
    [accessToken, permissions, identity, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// oxlint-disable-next-line react/only-export-components -- hook exposto junto do provider
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth deve ser usado dentro de um AuthProvider.');
  }

  return context;
}
