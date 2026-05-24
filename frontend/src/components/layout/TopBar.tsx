import { useLocation } from 'react-router-dom'
import { Bell, ChevronRight } from 'lucide-react'
import { useWSStore } from '@/stores/ws.store'
import { useAuthStore } from '@/stores/auth.store'
import { cn } from '@/lib/utils'

const ROUTE_LABELS: Record<string, string> = {
  '/': 'Dashboard',
  '/engagement': 'Engagement Hub',
  '/audit-program': 'Audit Program',
  '/exceptions': 'Exception Register',
  '/suam': 'Schedule of Unadjusted Misstatements',
  '/risk': 'Risk Assessment',
  '/regulatory': 'Regulatory Library',
  '/analytics': 'Analytics Wizard',
  '/financial': 'Financial Analytics',
  '/credit-policy': 'Credit Policy',
  '/ecl': 'ECL Intelligence',
  '/evidence': 'Document Vault',
  '/completion': 'Completion Center',
  '/team': 'Team Tracker',
  '/import-export': 'Import / Export',
}

export function TopBar() {
  const { pathname } = useLocation()
  const { activeUsers, events } = useWSStore()
  const { user } = useAuthStore()
  const pageLabel = ROUTE_LABELS[pathname] ?? 'Page'
  const unreadCount = events.filter(e => Date.now() - new Date(e.timestamp).getTime() < 60000).length

  return (
    <div className="flex h-14 items-center justify-between border-b bg-white px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span>NBFC Audit</span>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="font-medium text-gray-900">{pageLabel}</span>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Active users */}
        {activeUsers.length > 0 && (
          <div className="flex items-center gap-1">
            <div className="flex -space-x-2">
              {activeUsers.slice(0, 4).map(u => (
                <div
                  key={u.user_name}
                  title={u.user_name}
                  className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-primary-100 text-xs font-semibold text-primary-700"
                >
                  {u.user_name.slice(0, 2).toUpperCase()}
                </div>
              ))}
              {activeUsers.length > 4 && (
                <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white bg-gray-100 text-xs text-gray-600">
                  +{activeUsers.length - 4}
                </div>
              )}
            </div>
            <span className="text-xs text-gray-500">{activeUsers.length} online</span>
          </div>
        )}

        {/* Notifications */}
        <button className="relative rounded-full p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>

        {/* User avatar */}
        <div
          className={cn(
            'flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700'
          )}
        >
          {user?.full_name?.slice(0, 2).toUpperCase() ?? 'AU'}
        </div>
      </div>
    </div>
  )
}
