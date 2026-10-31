import { Menu } from '../ui/icons';

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  return (
    <header className="flex h-16 items-center gap-3 border-b border-border bg-surface px-4 md:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Abrir Menu"
        className="rounded-md p-2 text-slate-600 hover:bg-slate-100 md:hidden"
      >
        <Menu className="h-6 w-6" />
      </button>
      <span className="text-sm font-medium text-muted">Console de Gestão</span>
    </header>
  );
}
