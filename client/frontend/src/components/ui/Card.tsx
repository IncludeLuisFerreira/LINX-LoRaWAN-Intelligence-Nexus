import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';

interface CardProps {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, action, children, className }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-surface shadow-sm',
        className,
      )}
    >
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          {title && (
            <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
          )}
          {action}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
