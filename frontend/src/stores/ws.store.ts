import { create } from 'zustand'
import type { WSEvent, ActivityFeedItem } from '@/types'

interface ActiveUser {
  user_name: string
  joined_at: string
}

interface WSStore {
  events: ActivityFeedItem[]
  activeUsers: ActiveUser[]
  addEvent: (event: WSEvent) => void
  clearEvents: () => void
  setActiveUsers: (users: ActiveUser[]) => void
}

let eventCounter = 0

function formatEventMessage(event: WSEvent): string {
  switch (event.type) {
    case 'CAP_STATUS_UPDATED': {
      const p = event.payload as Record<string, string>
      return `${event.user_name ?? 'Someone'} updated ${p.seq_number ?? 'a procedure'} to ${p.status ?? 'new status'}`
    }
    case 'EXCEPTION_ADDED':
      return `${event.user_name ?? 'Someone'} added a new exception`
    case 'SUAM_RECALCULATED':
      return 'SUAM recalculated — check opinion'
    case 'ANALYTICS_JOB_COMPLETE': {
      const p = event.payload as Record<string, string>
      return `Analytics job ${p.da_ref ?? ''} completed — ${p.exceptions_found ?? 0} exceptions`
    }
    case 'USER_JOINED':
      return `${event.user_name ?? 'Someone'} joined the engagement`
    case 'USER_LEFT':
      return `${event.user_name ?? 'Someone'} left the engagement`
    default:
      return 'Activity recorded'
  }
}

export const useWSStore = create<WSStore>((set) => ({
  events: [],
  activeUsers: [],
  addEvent: (event) => {
    const item: ActivityFeedItem = {
      id: `evt-${++eventCounter}`,
      type: event.type,
      message: formatEventMessage(event),
      user_name: event.user_name,
      timestamp: event.timestamp,
    }
    set((state) => {
      // Update active users on join/leave
      if (event.type === 'USER_JOINED' && event.user_name) {
        const already = state.activeUsers.find(u => u.user_name === event.user_name)
        if (!already) {
          return {
            events: [item, ...state.events].slice(0, 50),
            activeUsers: [...state.activeUsers, { user_name: event.user_name, joined_at: event.timestamp }],
          }
        }
      }
      if (event.type === 'USER_LEFT' && event.user_name) {
        return {
          events: [item, ...state.events].slice(0, 50),
          activeUsers: state.activeUsers.filter(u => u.user_name !== event.user_name),
        }
      }
      return { events: [item, ...state.events].slice(0, 50) }
    })
  },
  clearEvents: () => set({ events: [] }),
  setActiveUsers: (users) => set({ activeUsers: users }),
}))
