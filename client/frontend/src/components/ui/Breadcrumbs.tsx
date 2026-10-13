import { Link } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1.5 text-sm">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
              {index > 0 && <span className="text-slate-300">/</span>}
              {item.to && !isLast ? (
                <Link
                  to={item.to}
                  className="text-muted transition-colors hover:text-primary-600"
                >
                  {item.label}
                </Link>
              ) : (
                <span className="font-medium text-slate-700">{item.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
