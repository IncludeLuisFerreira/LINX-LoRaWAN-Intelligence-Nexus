import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';

type AlertVariant = 'error' | 'success' | 'info';

const variants: Record<AlertVariant, string> = {
  error: 'bg-red-50 border-red-200 text-red-700',
  success: 'bg-green-50 border-green-200 text-green-700',
  info: 'bg-blue-50 border-blue-200 text-blue-700',
};

interface AlertProps {
  variant?: AlertVariant;
  children: ReactNode;
  onRetry?: () => void;
  className?: string;
}

export function Alert({
  variant = 'info',
  children,
  onRetry,
  className,
}: AlertProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm',
        variants[variant],
        className,
      )}
    >
      <span>{children}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 font-semibold underline underline-offset-2 hover:opacity-80"
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}
