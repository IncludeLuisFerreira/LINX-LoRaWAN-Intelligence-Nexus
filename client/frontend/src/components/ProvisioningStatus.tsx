import { cn } from '../utils/cn';
import type { ProvisioningStatusValue } from '../services/app';

interface ProvisioningStatusProps {
  status: ProvisioningStatusValue;
  className?: string;
}

/**
 * Rótulo e classes visuais de cada estado de provisionamento. As classes
 * seguem o contrato definido na issue #54.
 */
const STATUS_CONFIG = {
  PENDING: {
    label: 'Pendente',
    styles: 'bg-gray-100 text-gray-600',
  },
  PROVISIONING: {
    label: 'Provisionando',
    styles: 'bg-yellow-100 text-yellow-700 animate-pulse',
  },
  RUNNING: {
    label: 'Em execução',
    styles: 'bg-green-100 text-green-700',
  },
  ERROR: {
    label: 'Erro',
    styles: 'bg-red-100 text-red-700',
  },
} satisfies Record<ProvisioningStatusValue, { label: string; styles: string }>;

/**
 * Badge de apresentação do status de provisionamento. Não busca dados nem
 * mantém estado: o status deve vir do polling da issue #55.
 */
export function ProvisioningStatus({
  status,
  className,
}: ProvisioningStatusProps) {
  const config = STATUS_CONFIG[status];

  return (
    <span
      role="status"
      aria-live="polite"
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        config.styles,
        className,
      )}
    >
      {config.label}
    </span>
  );
}
