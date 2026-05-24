import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Clock, TrendingUp, CheckCircle, Activity } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { useEngagementStore } from '@/stores/engagement.store'
import { useWSStore } from '@/stores/ws.store'
import { getCAPProcedures } from '@/api/cap'
import { getEngagement } from '@/api/engagement'
import { getSUAMEntries } from '@/api/suam'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { RiskBadge } from '@/components/shared/RiskBadge'
import { ProgressRing } from '@/components/shared/ProgressRing'
import { EmptyState } from '@/components/shared/EmptyState'
import { formatCrore, formatDate, daysUntil, PHASE_LABELS } from '@/lib/utils'
import type { Phase } from '@/types'
import { CAP_PROCEDURES } from '@/data/cap-procedures'

const PHASES: Phase[] = ['planning', 'risk_assessment', 'controls', 'substantive', 'completion']

const PHASE_COLORS: Record<Phase, string> = {
  planning: '#818cf8',
  risk_assessment: '#60a5fa',
  controls: '#22d3ee',
  substantive: '#f59e0b',
  completion: '#10b981',
}

export function DashboardPage() {
  const { currentEngagementId, currentEngagement } = useEngagementStore()
  const { events } = useWSStore()

  const { data: engagement } = useQuery({
    queryKey: ['engagement', currentEngagementId],
    queryFn: () => getEngagement(currentEngagementId!),
    enabled: !!currentEngagementId,
    initialData: currentEngagement ?? undefined,
  })

  const { data: procedures = [], isLoading: procLoading } = useQuery({
    queryKey: ['cap', currentEngagementId],
    queryFn: () => getCAPProcedures(currentEngagementId!),
    enabled: !!currentEngagementId,
  })

  const { data: suamEntries = [] } = useQuery({
    queryKey: ['suam', currentEngagementId],
    queryFn: () => getSUAMEntries(currentEngagementId!),
    enabled: !!currentEngagementId,
  })

  // Use static CAP procedures as fallback
  const displayProcs = procedures.length > 0 ? procedures : CAP_PROCEDURES.map((p, i) => ({
    ...p,
    id: `static-${i}`,
    engagement_id: currentEngagementId ?? 'demo',
    status: 'pending' as const,
    assigned_to: null,
    budget_hours: null,
    actual_hours: null,
    start_date: null,
    completion_date: null,
    team_response: '',
    exceptions_found: false,
    observation: '',
    reviewer_comments: '',
    review_status: 'not_reviewed' as const,
    reviewed_by: null,
    reviewed_at: null,
    updated_at: new Date().toISOString(),
  }))

  // Phase stats
  const phaseStats = PHASES.map(phase => {
    const procs = displayProcs.filter(p => p.phase === phase)
    const completed = procs.filter(p => p.status === 'completed').length
    return { phase, total: procs.length, completed, pct: procs.length > 0 ? Math.round((completed / procs.length) * 100) : 0 }
  })

  // Overall stats
  const total = displayProcs.length
  const completed = displayProcs.filter(p => p.status === 'completed').length
  const inProgress = displayProcs.filter(p => p.status === 'in_progress').length
  const exceptions = displayProcs.filter(p => p.exceptions_found).length

  // Budget chart data
  const teamData = engagement?.team_roster?.map(m => ({
    name: m.staff_code || m.name.split(' ')[0],
    Budget: m.max_hours,
    Actual: Math.round(m.max_hours * 0.6 + Math.random() * 20), // demo
  })) ?? []

  // SUAM alert
  const pm = engagement?.performance_materiality ?? 0
  const uncorrectedSUAM = suamEntries.filter(s => !s.is_corrected).reduce((sum, s) => sum + s.amount_crore, 0)
  const suamAlert = pm > 0 && uncorrectedSUAM > pm

  const daysLeft = daysUntil(engagement?.target_report_date)

  return (
    <div className="p-6 space-y-6">
      {/* SUAM Alert */}
      {suamAlert && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
          <div>
            <p className="text-sm font-semibold text-red-700">SUAM Alert — Uncorrected Misstatements Exceed PM</p>
            <p className="mt-0.5 text-sm text-red-600">
              Total uncorrected: {formatCrore(uncorrectedSUAM)} | PM: {formatCrore(pm)} — Modified opinion may be required (SA 705)
            </p>
          </div>
        </div>
      )}

      {/* Engagement Summary */}
      {engagement ? (
        <div className="rounded-xl border bg-white p-6">
          <div className="flex items-start justify-between">
            <div>
              <h1>{engagement.client_name}</h1>
              <p className="mt-1 text-sm text-gray-500">
                {engagement.audit_firm_name} | {engagement.file_reference}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <RiskBadge rating={engagement.risk_level ?? 'medium'} />
              {daysLeft !== null && (
                <span className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
                  daysLeft < 14 ? 'bg-red-100 text-red-700' : daysLeft < 30 ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                }`}>
                  <Clock className="h-3 w-3" />
                  {daysLeft > 0 ? `${daysLeft}d to report` : `${Math.abs(daysLeft)}d overdue`}
                </span>
              )}
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4 border-t pt-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-gray-500">Period</p>
              <p className="text-sm font-medium text-gray-900">
                {formatDate(engagement.period_from)} – {formatDate(engagement.period_to)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Overall Materiality</p>
              <p className="text-sm font-medium text-gray-900">{formatCrore(engagement.overall_materiality)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Performance Materiality</p>
              <p className="text-sm font-medium text-gray-900">{formatCrore(engagement.performance_materiality)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">NBFC Layer</p>
              <p className="text-sm font-medium text-gray-900">{engagement.nbfc_layer || '—'}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border bg-white p-6">
          <EmptyState
            icon={AlertTriangle}
            title="No engagement selected"
            description="Go to Engagement Hub to configure your engagement"
          />
        </div>
      )}

      {/* Phase Progress */}
      <div className="grid grid-cols-5 gap-4">
        {phaseStats.map(({ phase, total, completed, pct }) => (
          <div key={phase} className="rounded-xl border bg-white p-5 text-center">
            <ProgressRing
              value={pct}
              size={72}
              color={PHASE_COLORS[phase]}
              label={`${completed}/${total}`}
              sublabel="done"
            />
            <p className="mt-3 text-xs font-medium text-gray-700">{PHASE_LABELS[phase]}</p>
            <p className="text-xs text-gray-400">{pct}% complete</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* RAG Status Table */}
        <div className="col-span-2 rounded-xl border bg-white">
          <div className="flex items-center justify-between border-b px-5 py-4">
            <h2 className="text-base font-semibold text-gray-900">Audit Progress</h2>
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <span className="inline-block h-2 w-2 rounded-full bg-green-400" /> {completed} Completed
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <span className="inline-block h-2 w-2 rounded-full bg-amber-400" /> {inProgress} In Progress
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <span className="inline-block h-2 w-2 rounded-full bg-red-400" /> {exceptions} Exceptions
              </span>
            </div>
          </div>
          {procLoading ? (
            <div className="p-8 text-center text-sm text-gray-400">Loading procedures…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs font-medium text-gray-500">
                    <th className="px-4 py-3 text-left">Seq</th>
                    <th className="px-4 py-3 text-left">Procedure</th>
                    <th className="px-4 py-3 text-left">Phase</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Assignee</th>
                    <th className="px-4 py-3 text-right">Hrs</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {displayProcs.slice(0, 15).map(p => {
                    const isOverdue = p.completion_date
                      ? new Date(p.completion_date) < new Date() && p.status !== 'completed'
                      : false
                    return (
                      <tr key={p.id} className={`hover:bg-gray-50 ${isOverdue ? 'bg-red-50' : ''}`}>
                        <td className="px-4 py-2.5 font-mono text-xs font-medium text-gray-700">{p.seq_number}</td>
                        <td className="max-w-xs px-4 py-2.5">
                          <span className="truncate block text-xs text-gray-800">{p.procedure_name}</span>
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-500">{PHASE_LABELS[p.phase]}</td>
                        <td className="px-4 py-2.5">
                          <StatusBadge status={p.status} size="sm" />
                        </td>
                        <td className="px-4 py-2.5 text-xs text-gray-500">{p.assigned_to ?? '—'}</td>
                        <td className="px-4 py-2.5 text-right text-xs text-gray-500">
                          {p.actual_hours ?? '—'}/{p.budget_hours ?? '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="rounded-xl border bg-white">
          <div className="border-b px-5 py-4">
            <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
              <Activity className="h-4 w-4 text-primary-500" />
              Live Activity
            </h2>
          </div>
          <div className="divide-y overflow-y-auto max-h-80">
            {events.length === 0 ? (
              <div className="p-6 text-center text-xs text-gray-400">No activity yet</div>
            ) : (
              events.slice(0, 20).map(evt => (
                <div key={evt.id} className="px-4 py-3">
                  <p className="text-xs text-gray-700">{evt.message}</p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                    {evt.user_name && ` · ${evt.user_name}`}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Budget Chart */}
      {teamData.length > 0 && (
        <div className="rounded-xl border bg-white p-6">
          <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-gray-900">
            <TrendingUp className="h-4 w-4 text-primary-500" />
            Team Hours: Budget vs Actual
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={teamData} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Budget" fill="#e0e7ff" radius={[3, 3, 0, 0]} />
              <Bar dataKey="Actual" fill="#6366f1" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Active Blockers */}
      <div className="rounded-xl border bg-white">
        <div className="border-b px-5 py-4">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            Active Blockers
          </h2>
        </div>
        <div className="p-4">
          {displayProcs.filter(p => p.observation?.toLowerCase().includes('blocker') || p.status === 'in_progress').length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <CheckCircle className="h-4 w-4" />
              No blockers — engagement is on track
            </div>
          ) : (
            <div className="space-y-2">
              {displayProcs
                .filter(p => p.observation?.toLowerCase().includes('blocker') || (p.status === 'in_progress' && !p.assigned_to))
                .slice(0, 5)
                .map(p => (
                  <div key={p.id} className="flex items-center justify-between rounded-lg bg-amber-50 px-3 py-2">
                    <div>
                      <span className="text-xs font-mono font-medium text-gray-700">{p.seq_number}</span>
                      <span className="ml-2 text-xs text-gray-600">{p.procedure_name}</span>
                    </div>
                    <StatusBadge status={p.status} size="sm" />
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
