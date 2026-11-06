import type { ReactNode } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface CanProps {
  /** Permissão exigida, no formato `resource:action` (ex.: `device:create`). */
  permission: string;
  children: ReactNode;
}

/**
 * Renderiza os filhos somente quando o usuário autenticado possui a permissão.
 * As permissões são lidas da claim `permissions` do JWT pelo AuthContext.
 */
export function Can({ permission, children }: CanProps) {
  const { permissions } = useAuth();

  if (!permissions.includes(permission)) {
    return null;
  }

  return <>{children}</>;
}
