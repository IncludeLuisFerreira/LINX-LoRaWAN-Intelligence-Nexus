interface AppBarProps {
  onMenuClick: () => void;
}

export function AppBar({ onMenuClick }: AppBarProps) {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/50 px-4 flex items-center justify-between">
      <button
        type="button"
        className="p-2 rounded-md text-slate-300 hover:bg-slate-800 md:hidden"
        onClick={onMenuClick}
        aria-label="Abrir Menu"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>

      <div className="text-sm text-slate-400 font-medium">
        Painel de Controle
      </div>
    </header>
  );
}
