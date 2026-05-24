import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Building2, ClipboardList, AlertTriangle,
  BarChart3, BookOpen, Database, CreditCard, TrendingUp,
  Brain, FileBox, CheckSquare, Users, Settings, ChevronDown,
  LogOut, FileWarning, Layers
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth.store'
import { useEngagementStore } from '@/stores/engagement.store'
import { useState } from 'react'

interface NavItem {
  label: string
  to: string
  icon: React.ElementType
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'OVERVIEW',
    items: [
      { label: 'Dashboard', to: '/', icon: LayoutDashboard },
      { label: 'Engagement Hub', to: '/engagement', icon: Building2 },
    ],
  },
  {
    label: 'AUDIT EXECUTION',
    items: [
      { label: 'Audit Program', to: '/audit-program', icon: ClipboardList },
    ],
  },
  {
    label: 'FINDINGS',
    items: [
      { label: 'Exception Register', to: '/exceptions', icon: AlertTriangle },
      { label: 'SUAM', to: '/suam', icon: FileWarning },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { label: 'Risk Assessment', to: '/risk', icon: BarChart3 },
      { label: 'Regulatory Library', to: '/regulatory', icon: BookOpen },
    ],
  },
  {
    label: 'DATA ANALYTICS',
    items: [
      { label: 'Analytics Wizard', to: '/analytics', icon: Database },
      { label: 'Credit Policy', to: '/credit-policy', icon: CreditCard },
    ],
  },
  {
    label: 'FINANCIAL',
    items: [
      { label: 'Financial Analytics', to: '/financial', icon: TrendingUp },
      { label: 'ECL Intelligence', to: '/ecl', icon: Brain },
    ],
  },
  {
    label: 'EVIDENCE',
    items: [
      { label: 'Document Vault', to: '/evidence', icon: FileBox },
    ],
  },
  {
    label: 'COMPLETION',
    items: [
      { label: 'Completion Center', to: '/completion', icon: CheckSquare },
      { label: 'Team Tracker', to: '/team', icon: Users },
    ],
  },
  {
    label: 'SETTINGS',
    items: [
      { label: 'Import / Export', to: '/import-export', icon: Settings },
    ],
  },
]

export function Sidebar() {
  const { user, logout } = useAuthStore()
  const { currentEngagement } = useEngagementStore()
  const navigate = useNavigate()
  const [engExpanded, setEngExpanded] = useState(true)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-full w-56 flex-col border-r bg-white">
      {/* Logo */}
      <div className="flex items-center gap-2 border-b px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-500">
          <Layers className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">NBFC Audit</p>
          <p className="text-xs text-gray-500">Intelligence Platform</p>
        </div>
      </div>

      {/* Engagement Context */}
      {currentEngagement && (
        <button
          onClick={() => setEngExpanded(!engExpanded)}
          className="flex items-center justify-between border-b px-4 py-3 text-left hover:bg-gray-50"
        >
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-gray-900">
              {currentEngagement.client_name}
            </p>
            <p className="text-xs text-gray-500">
              {currentEngagement.period_to?.slice(0, 7)}
            </p>
          </div>
          <ChevronDown className={cn('ml-2 h-3 w-3 flex-shrink-0 text-gray-400 transition-transform', engExpanded && 'rotate-180')} />
        </button>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {NAV_GROUPS.map(group => (
          <div key={group.label} className="mb-4">
            <p className="mb-1 px-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
              {group.label}
            </p>
            {group.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-600 font-medium'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  )
                }
              >
                <item.icon className="h-4 w-4 flex-shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* User */}
      <div className="border-t p-3">
        <div className="flex items-center justify-between rounded-lg px-2 py-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              {user?.full_name?.slice(0, 2).toUpperCase() ?? 'AU'}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-gray-900">{user?.full_name ?? 'Auditor'}</p>
              <p className="truncate text-xs text-gray-500">{user?.role ?? 'user'}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="ml-2 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            title="Logout"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
