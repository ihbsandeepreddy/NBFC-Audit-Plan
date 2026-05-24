import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { useCallback } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useEngagementStore } from '@/stores/engagement.store'
import { useWSStore } from '@/stores/ws.store'
import { useQueryClient } from '@tanstack/react-query'
import type { WSEvent } from '@/types'

export default function AppLayout() {
  const { currentEngagementId } = useEngagementStore()
  const { addEvent } = useWSStore()
  const queryClient = useQueryClient()

  const onMessage = useCallback((event: WSEvent) => {
    addEvent(event)
    // Invalidate relevant queries on WS events
    if (event.type === 'CAP_STATUS_UPDATED') {
      queryClient.invalidateQueries({ queryKey: ['cap', currentEngagementId] })
    }
    if (event.type === 'EXCEPTION_ADDED') {
      queryClient.invalidateQueries({ queryKey: ['exceptions', currentEngagementId] })
    }
    if (event.type === 'SUAM_RECALCULATED') {
      queryClient.invalidateQueries({ queryKey: ['suam', currentEngagementId] })
    }
  }, [addEvent, queryClient, currentEngagementId])

  useWebSocket(currentEngagementId, onMessage)

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
