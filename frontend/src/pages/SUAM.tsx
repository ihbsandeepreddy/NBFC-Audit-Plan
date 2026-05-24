import { useEngagementStore } from '@/stores/engagement.store'
import { useAuthStore } from '@/stores/auth.store'

export function SUAMPage() {
  const { currentEngagementId } = useEngagementStore()
  const { user } = useAuthStore()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Schedule of Unadjusted Misstatements</h1>
        <p className="mt-1 text-sm text-gray-500">Engagement ID: {currentEngagementId}</p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <p className="text-gray-600">Content for Schedule of Unadjusted Misstatements coming soon.</p>
      </div>
    </div>
  )
}
