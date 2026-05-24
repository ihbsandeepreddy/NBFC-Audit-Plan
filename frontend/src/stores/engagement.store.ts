import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Engagement } from '@/types'

interface EngagementStore {
  currentEngagement: Engagement | null
  currentEngagementId: string | null
  setCurrentEngagement: (engagement: Engagement) => void
  setCurrentEngagementId: (id: string) => void
  clearEngagement: () => void
}

export const useEngagementStore = create<EngagementStore>()(
  persist(
    (set) => ({
      currentEngagement: null,
      currentEngagementId: null,
      setCurrentEngagement: (engagement) =>
        set({ currentEngagement: engagement, currentEngagementId: engagement.id }),
      setCurrentEngagementId: (id) => set({ currentEngagementId: id }),
      clearEngagement: () => set({ currentEngagement: null, currentEngagementId: null }),
    }),
    { name: 'engagement-storage' }
  )
)
