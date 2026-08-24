import { useEffect, useState } from 'react'
import { Header } from './components/Header'
import { DeviceCards } from './components/DeviceCards'
import { RealtimeChart } from './components/RealtimeChart'
import { AlertsPanel } from './components/AlertsPanel'
import { HistoryTable } from './components/HistoryTable'
import { useTelemetrySocket } from './hooks/useTelemetrySocket'

export default function App() {
  const { connected, buffer } = useTelemetrySocket()
  const [dark, setDark] = useState(true)
  const [selectedDevice, setSelectedDevice] = useState<string | undefined>()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  const deviceEuis = Object.keys(buffer)
  const activeEui =
    selectedDevice && buffer[selectedDevice] ? selectedDevice : deviceEuis[0]
  const chartData = activeEui ? buffer[activeEui] ?? [] : []

  return (
    <div className="min-h-screen bg-gray-100 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      <Header connected={connected} dark={dark} onToggleTheme={() => setDark((d) => !d)} />
      <main className="mx-auto max-w-7xl space-y-6 p-6">
        <DeviceCards buffer={buffer} selectedDevice={selectedDevice} onSelect={setSelectedDevice} />
        <RealtimeChart data={chartData} />
        <AlertsPanel />
        <HistoryTable />
      </main>
    </div>
  )
}
