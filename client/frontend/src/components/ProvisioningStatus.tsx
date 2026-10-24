import { cn } from '../utils/cn';

export type ProvisioningState =
  'PENDING' | 'PROVISIONING' | 'RUNNING' | 'ERROR';

interface ProvisioningStatusProps {
  status: ProvisioningState;
  className?: string;
}

const STATUS_CONFIG: Record<
  ProvisioningState,
  { label: string; styles: string }
> = {
  PENDING: {
    label: 'Pendente',
    styles: 'bg-gray-100 text-gray-700',
  },
  PROVISIONING: {
    label: 'Provisionando',
    styles: 'bg-yellow-100 text-yellow-800',
  },
  RUNNING: {
    label: 'Em execução',
    styles: 'bg-green-100 text-green-800',
  },
  ERROR: {
    label: 'Erro',
    styles: 'bg-red-100 text-red-800 ring-1 ring-red-300 font-semibold',
  },
};

export function ProvisioningStatus({
  status,
  className,
}: ProvisioningStatusProps) {
  const config = STATUS_CONFIG[status];
  const isProvisioning = status === 'PROVISIONING';

  return (
    <span
      role="status"
      aria-live="polite"
      aria-label={`Status de provisionamento: ${config.label}`}
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium',
        config.styles,
        isProvisioning && 'animate-pulse',
        className,
      )}
    >
      {isProvisioning && (
        <span
          aria-hidden="true"
          className="h-3 w-3 animate-spin rounded-full border-2 border-current border-r-transparent"
        />
      )}

      {config.label}
    </span>
  );
}
