import { useEngagementStore } from '@/stores/engagement.store'

export function EngagementPage() {
  const { currentEngagement } = useEngagementStore()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Engagement Hub</h1>
        <p className="mt-1 text-sm text-gray-500">
          {currentEngagement?.client_name ?? 'No engagement selected'}
        </p>
      </div>
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <p className="text-gray-600">Engagement details and team roster.</p>
      </div>
    </div>
  )
}
