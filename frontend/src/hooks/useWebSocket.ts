import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/stores/auth.store'
import type { WSEvent } from '@/types'

export function useWebSocket(engagementId: string | null, onMessage: (event: WSEvent) => void) {
  const ws = useRef<WebSocket | null>(null)
  const { token } = useAuthStore()
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const shouldReconnect = useRef(true)

  const connect = useCallback(() => {
    if (!engagementId || !token) return
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${window.location.host}/ws/${engagementId}?token=${token}`

    try {
      ws.current = new WebSocket(url)

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSEvent
          onMessage(data)
        } catch {
          // ignore parse errors
        }
      }

      ws.current.onclose = () => {
        if (shouldReconnect.current) {
          reconnectTimer.current = setTimeout(connect, 3000)
        }
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }
    } catch {
      // WebSocket not available (e.g. in test/dev without backend)
    }
  }, [engagementId, token, onMessage])

  useEffect(() => {
    shouldReconnect.current = true
    connect()
    return () => {
      shouldReconnect.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  const send = useCallback((event: WSEvent) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(event))
    }
  }, [])

  return { send }
}
