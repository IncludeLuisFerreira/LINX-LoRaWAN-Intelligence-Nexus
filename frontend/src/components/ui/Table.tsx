import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';

export interface Column<T> {
  key: string;
  header: string;
  className?: string;
  render?: (row: T) => ReactNode;
}

interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: ReactNode;
}

export function Table<T>({ columns, rows, rowKey, empty }: TableProps<T>) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-slate-50 text-left">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  'px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted',
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className="border-b border-border last:border-0 hover:bg-slate-50"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn('px-4 py-3 text-slate-700', column.className)}
                >
                  {column.render
                    ? column.render(row)
                    : ((row as Record<string, ReactNode>)[column.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
