import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';

type BadgeColor = 'blue' | 'gray' | 'green' | 'red';

const colors: Record<BadgeColor, string> = {
  blue: 'bg-blue-50 text-blue-700 ring-blue-200',
  gray: 'bg-slate-100 text-slate-600 ring-slate-200',
  green: 'bg-green-50 text-green-700 ring-green-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
};

interface BadgeProps {
  color?: BadgeColor;
  children: ReactNode;
  className?: string;
}

export function Badge({ color = 'gray', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        colors[color],
        className,
      )}
    >
      {children}
    </span>
  );
}
