import { useEffect, useState } from 'react'
import type { Reading } from '../types'
import { connectSocket } from '../socket/socket'

const BUFFER_SIZE = 60

export function useTelemetrySocket() {
  const [connected, setConnected] = useState(false)
  const [buffer, setBuffer] = useState<Record<string, Reading[]>>({})

  useEffect(() => {
    const socket = connectSocket()
    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))
    socket.on('telemetry:new', (reading: Reading) => {
      setBuffer((prev) => {
        const arr = prev[reading.deviceEui] ?? []
        const next = [...arr, reading]
        if (next.length > BUFFER_SIZE) next.splice(0, next.length - BUFFER_SIZE)
        return { ...prev, [reading.deviceEui]: next }
      })
    })
    return () => {
      socket.off('connect')
      socket.off('disconnect')
      socket.off('telemetry:new')
    }
  }, [])

  return { connected, buffer }
}
