import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: number | string;
  icon?: ReactNode;
}

export function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-border bg-surface p-5 shadow-sm">
      {icon && (
        <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
          {icon}
        </span>
      )}
      <div>
        <p className="text-2xl font-semibold text-slate-800">{value}</p>
        <p className="text-xs font-medium uppercase tracking-wide text-muted">
          {label}
        </p>
      </div>
    </div>
  );
}
