interface HeaderProps {
  connected: boolean
  dark: boolean
  onToggleTheme: () => void
}

export function Header({ connected, dark, onToggleTheme }: HeaderProps) {
  return (
    <header className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">ChirpStack Dashboard</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Telemetria LoRaWAN em tempo real</p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
              connected
                ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            {connected ? 'Conectado' : 'Desconectado'}
          </span>
          <button
            onClick={onToggleTheme}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200"
          >
            {dark ? '☀️ Claro' : '🌙 Escuro'}
          </button>
        </div>
      </div>
    </header>
  )
}
