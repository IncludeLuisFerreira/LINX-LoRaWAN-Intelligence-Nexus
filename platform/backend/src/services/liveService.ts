import type { Server } from 'socket.io'
import type { Reading } from '../types'

export interface LiveService {
  emitReading(reading: Reading): void
}

export function setupLiveService(io: Server): LiveService {
  io.on('connection', () => {
    io.emit('server:status', { online: true })
  })
  return {
    emitReading(reading: Reading): void {
      io.emit('telemetry:new', reading)
    },
  }
}
