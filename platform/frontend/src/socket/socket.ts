import { io, type Socket } from 'socket.io-client'

let socket: Socket | null = null

export function connectSocket(): Socket {
  if (socket) return socket
  socket = io()
  return socket
}
