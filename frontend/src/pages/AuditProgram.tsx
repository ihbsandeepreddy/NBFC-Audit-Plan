import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, X, ChevronRight, Save, AlertTriangle, Clock } from 'lucide-react'
import { useEngagementStore } from '@/stores/engagement.store'
import { getCAPProcedures, updateCAPProcedure } from '@/api/cap'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { RiskBadge } from '@/components/shared/RiskBadge'
import { PhaseHeader } from '@/components/shared/PhaseHeader'
import { EmptyState } from '@/components/shared/EmptyState'
import { cn, PHASE_LABELS, PHASE_COLORS } from '@/lib/utils'
import { CAP_PROCEDURES } from '@/data/cap-procedures'
import type { CAPProcedure, Phase, ProcedureStatus, ReviewStatus } from '@/types'

const PHASES: Phase[] = ['planning', 'risk_assessment', 'controls', 'substantive', 'completion']

function buildDisplayProcs(apiProcs: CAPProcedure[]): CAPProcedure[] {
  if (apiProcs.length > 0) return apiProcs
  return CAP_PROCEDURES.map((p, i) => ({
    ...p,
    id: `static-${i}`,
    engagement_id: 'demo',
    status: 'pending' as ProcedureStatus,
    assigned_to: null,
    budget_hours: null,
    actual_hours: null,
    start_date: null,
    completion_date: null,
    team_response: p.template_team_response ?? '',
    exceptions_found: false,
    observation: '',
    reviewer_comments: '',
    review_status: 'not_reviewed' as ReviewStatus,
    reviewed_by: null,
    reviewed_at: null,
    updated_at: new Date().toISOString(),
  }))
}

interface DrawerProps {
  procedure: CAPProcedure
  onClose: () => void
  onSave: (updates: Partial<CAPProcedure>) => void
  isSaving: boolean
  teamMembers: string[]
}

function ProcedureDrawer({ procedure, onClose, onSave, isSaving, teamMembers }: DrawerProps) {
  const [local, setLocal] = useState<Partial<CAPProcedure>>({
    status: procedure.status,
    assigned_to: procedure.assigned_to,
    budget_hours: procedure.budget_hours,
    actual_hours: procedure.actual_hours,
    start_date: procedure.start_date,
    completion_date: procedure.completion_date,
    team_response: procedure.team_response || procedure.template_team_response || '',
    exceptions_found: procedure.exceptions_found,
    observation: procedure.observation,
    reviewer_comments: procedure.reviewer_comments,
    review_status: procedure.review_status,
  })

  const update = (field: keyof CAPProcedure, value: unknown) => {
    setLocal(prev => ({ ...prev, [field]: value }))
  }

  // Highlight [X], [Y], [Z], [A], [B] etc in team response
  const highlightedResponse = (text: string) =>
    text.replace(/\[([A-Z][a-z]?|[0-9]+[A-Za-z]*)\]/g, (match) =>
      `<mark class="bg-amber-100 text-amber-800 rounded px-0.5">${match}</mark>`
    )

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30" onClick={onClose} />

      {/* Drawer */}
      <div className="flex h-full w-[860px] flex-col border-l bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b px-6 py-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-xs font-medium text-gray-700">
                {procedure.seq_number}
              </span>
              <RiskBadge rating={procedure.risk_rating} />
              <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', PHASE_COLORS[procedure.phase])}>
                {PHASE_LABELS[procedure.phase]}
              </span>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-gray-900">{procedure.procedure_name}</h2>
            <p className="text-sm text-gray-500">{procedure.section} · WP: {procedure.wp_reference}</p>
          </div>
          <button onClick={onClose} className="rounded p-1.5 text-gray-400 hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left — Static details */}
          <div className="w-80 flex-shrink-0 overflow-y-auto border-r bg-gray-50 p-5 space-y-5">
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">Description</p>
              <p className="text-sm text-gray-700 leading-relaxed">{procedure.procedure_description}</p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">Assertion</p>
              <p className="text-sm text-gray-700">{procedure.assertion || '—'}</p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">Expected Control</p>
              <p className="text-sm text-gray-700">{procedure.expected_control || '—'}</p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">Documents to Obtain</p>
              <p className="text-sm text-gray-700">{procedure.documents_to_obtain || '—'}</p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">DA Step</p>
              <p className="text-sm text-gray-700">{procedure.data_analytics_step || 'N/A'}</p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">Regulatory Reference</p>
              <div className="rounded-lg bg-indigo-50 p-3">
                <p className="text-xs font-medium text-indigo-700">{procedure.regulatory_reference}</p>
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">Applicable To</p>
              <p className="text-sm text-gray-700">{procedure.applicable_to}</p>
            </div>
          </div>

          {/* Right — Dynamic / editable */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Status Toggle */}
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">Status</p>
              <div className="flex gap-1">
                {(['pending', 'in_progress', 'completed'] as ProcedureStatus[]).map(s => (
                  <button
                    key={s}
                    onClick={() => update('status', s)}
                    className={cn(
                      'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                      local.status === s
                        ? s === 'completed' ? 'bg-green-500 text-white'
                          : s === 'in_progress' ? 'bg-amber-500 text-white'
                          : 'bg-gray-500 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    )}
                  >
                    {s === 'in_progress' ? 'In Progress' : s === 'completed' ? 'Completed' : 'Pending'}
                  </button>
                ))}
              </div>
            </div>

            {/* Assigned To */}
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                Assigned To
              </label>
              <select
                value={local.assigned_to ?? ''}
                onChange={e => update('assigned_to', e.target.value || null)}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              >
                <option value="">Unassigned</option>
                {teamMembers.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            {/* Hours */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Budget Hours
                </label>
                <input
                  type="number"
                  value={local.budget_hours ?? ''}
                  onChange={e => update('budget_hours', e.target.value ? Number(e.target.value) : null)}
                  placeholder="0"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Actual Hours
                </label>
                <input
                  type="number"
                  value={local.actual_hours ?? ''}
                  onChange={e => update('actual_hours', e.target.value ? Number(e.target.value) : null)}
                  placeholder="0"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                />
              </div>
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Start Date
                </label>
                <input
                  type="date"
                  value={local.start_date ?? ''}
                  onChange={e => update('start_date', e.target.value || null)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Target Completion
                </label>
                <input
                  type="date"
                  value={local.completion_date ?? ''}
                  onChange={e => update('completion_date', e.target.value || null)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                />
              </div>
            </div>

            {/* Team Response */}
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                Team Response
                <span className="ml-2 text-xs font-normal normal-case text-amber-600">
                  Highlighted placeholders need to be filled in
                </span>
              </label>
              <textarea
                value={local.team_response ?? ''}
                onChange={e => update('team_response', e.target.value)}
                rows={8}
                placeholder="Document audit procedures performed, evidence obtained, and conclusions reached…"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              />
              {(local.team_response ?? '').includes('[') && (
                <p className="mt-1 flex items-center gap-1 text-xs text-amber-600">
                  <AlertTriangle className="h-3 w-3" />
                  Unfilled placeholders detected — please complete before marking complete
                </p>
              )}
            </div>

            {/* Exceptions Found */}
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium text-gray-900">Exceptions Found</p>
                <p className="text-xs text-gray-500">Toggle if exceptions were identified during this procedure</p>
              </div>
              <button
                onClick={() => update('exceptions_found', !local.exceptions_found)}
                className={cn(
                  'relative h-5 w-9 rounded-full transition-colors',
                  local.exceptions_found ? 'bg-red-500' : 'bg-gray-200'
                )}
              >
                <span className={cn(
                  'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform',
                  local.exceptions_found ? 'translate-x-4' : 'translate-x-0.5'
                )} />
              </button>
            </div>

            {/* Observation */}
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-400">
                Observation / Notes
              </label>
              <textarea
                value={local.observation ?? ''}
                onChange={e => update('observation', e.target.value)}
                rows={3}
                placeholder="Internal observation or notes for reviewer…"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              />
            </div>

            {/* Review */}
            <div className="rounded-lg border bg-gray-50 p-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Review</p>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-600">Review Status</label>
                <select
                  value={local.review_status ?? 'not_reviewed'}
                  onChange={e => update('review_status', e.target.value as ReviewStatus)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400"
                >
                  <option value="not_reviewed">Not Reviewed</option>
                  <option value="in_review">In Review</option>
                  <option value="approved">Approved</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-600">Reviewer Comments</label>
                <textarea
                  value={local.reviewer_comments ?? ''}
                  onChange={e => update('reviewer_comments', e.target.value)}
                  rows={3}
                  placeholder="Reviewer notes…"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-primary-400"
                />
              </div>
            </div>

            {/* Save Button */}
            <button
              onClick={() => onSave(local)}
              disabled={isSaving}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-600 disabled:opacity-60"
            >
              <Save className="h-4 w-4" />
              {isSaving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AuditProgram() {
  const { currentEngagementId, currentEngagement } = useEngagementStore()
  const queryClient = useQueryClient()

  const [selectedProc, setSelectedProc] = useState<CAPProcedure | null>(null)
  const [filters, setFilters] = useState({
    phase: 'all' as Phase | 'all',
    status: 'all',
    risk: 'all',
    assignee: 'all',
    exceptionsOnly: false,
    search: '',
  })

  const { data: procedures = [], isLoading } = useQuery({
    queryKey: ['cap', currentEngagementId],
    queryFn: () => getCAPProcedures(currentEngagementId!),
    enabled: !!currentEngagementId,
  })

  const displayProcs = buildDisplayProcs(procedures)

  const updateMutation = useMutation({
    mutationFn: ({ procId, updates }: { procId: string; updates: Partial<CAPProcedure> }) =>
      updateCAPProcedure(currentEngagementId!, procId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cap', currentEngagementId] })
      setSelectedProc(null)
    },
  })

  const handleSave = useCallback((updates: Partial<CAPProcedure>) => {
    if (!selectedProc) return
    updateMutation.mutate({ procId: selectedProc.id, updates })
  }, [selectedProc, updateMutation])

  const teamMembers = currentEngagement?.team_roster?.map(m => m.name) ?? []

  // Filtered procedures
  const filtered = useMemo(() => {
    return displayProcs.filter(p => {
      if (filters.phase !== 'all' && p.phase !== filters.phase) return false
      if (filters.status !== 'all' && p.status !== filters.status) return false
      if (filters.risk !== 'all' && p.risk_rating !== filters.risk) return false
      if (filters.assignee !== 'all' && p.assigned_to !== filters.assignee) return false
      if (filters.exceptionsOnly && !p.exceptions_found) return false
      if (filters.search && !p.procedure_name.toLowerCase().includes(filters.search.toLowerCase()) &&
          !p.seq_number.toLowerCase().includes(filters.search.toLowerCase())) return false
      return true
    })
  }, [displayProcs, filters])

  // Stats
  const stats = {
    total: displayProcs.length,
    completed: displayProcs.filter(p => p.status === 'completed').length,
    inProgress: displayProcs.filter(p => p.status === 'in_progress').length,
    pending: displayProcs.filter(p => p.status === 'pending').length,
    exceptions: displayProcs.filter(p => p.exceptions_found).length,
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1>Consolidated Audit Program</h1>
            <p className="text-sm text-gray-500">Manage all audit procedures across phases</p>
          </div>
          {/* Stats */}
          <div className="flex items-center gap-4">
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-900">{stats.total}</p>
              <p className="text-xs text-gray-500">Total</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-green-600">{stats.completed}</p>
              <p className="text-xs text-gray-500">Done</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-amber-600">{stats.inProgress}</p>
              <p className="text-xs text-gray-500">In Progress</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-gray-500">{stats.pending}</p>
              <p className="text-xs text-gray-500">Pending</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-red-600">{stats.exceptions}</p>
              <p className="text-xs text-gray-500">Exceptions</p>
            </div>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="mt-4 flex items-center gap-3 flex-wrap">
          {/* Search */}
          <div className="relative w-56">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              value={filters.search}
              onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
              placeholder="Search procedures…"
              className="w-full rounded-lg border border-gray-200 py-1.5 pl-8 pr-3 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
            />
          </div>

          {/* Phase */}
          <select
            value={filters.phase}
            onChange={e => setFilters(f => ({ ...f, phase: e.target.value as Phase | 'all' }))}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-primary-400"
          >
            <option value="all">All Phases</option>
            {PHASES.map(ph => <option key={ph} value={ph}>{PHASE_LABELS[ph]}</option>)}
          </select>

          {/* Status */}
          <select
            value={filters.status}
            onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-primary-400"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
          </select>

          {/* Risk */}
          <select
            value={filters.risk}
            onChange={e => setFilters(f => ({ ...f, risk: e.target.value }))}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-primary-400"
          >
            <option value="all">All Risk Ratings</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          {/* Assignee */}
          <select
            value={filters.assignee}
            onChange={e => setFilters(f => ({ ...f, assignee: e.target.value }))}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-primary-400"
          >
            <option value="all">All Assignees</option>
            {teamMembers.map(m => <option key={m} value={m}>{m}</option>)}
          </select>

          {/* Exceptions Only */}
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-gray-200 px-3 py-1.5">
            <input
              type="checkbox"
              checked={filters.exceptionsOnly}
              onChange={e => setFilters(f => ({ ...f, exceptionsOnly: e.target.checked }))}
              className="rounded border-gray-300 text-primary-500"
            />
            <span className="text-sm text-gray-600">Exceptions Only</span>
          </label>

          {/* Clear */}
          {(filters.search || filters.phase !== 'all' || filters.status !== 'all' || filters.risk !== 'all' || filters.exceptionsOnly) && (
            <button
              onClick={() => setFilters({ phase: 'all', status: 'all', risk: 'all', assignee: 'all', exceptionsOnly: false, search: '' })}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
            >
              <X className="h-3.5 w-3.5" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-gray-400">Loading audit program…</div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No procedures found"
            description="Try adjusting your filters"
          />
        ) : (
          PHASES.map(phase => {
            const phaseProcs = filtered.filter(p => p.phase === phase)
            if (phaseProcs.length === 0) return null
            const completed = phaseProcs.filter(p => p.status === 'completed').length

            return (
              <PhaseHeader
                key={phase}
                phase={phase}
                total={phaseProcs.length}
                completed={completed}
              >
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-xs font-medium text-gray-500">
                      <th className="px-4 py-2.5 text-left">Seq</th>
                      <th className="px-4 py-2.5 text-left">Section</th>
                      <th className="px-4 py-2.5 text-left">Procedure</th>
                      <th className="px-4 py-2.5 text-left">Applicable To</th>
                      <th className="px-4 py-2.5 text-left">Risk</th>
                      <th className="px-4 py-2.5 text-left">Assignee</th>
                      <th className="px-4 py-2.5 text-right">Hrs B/A</th>
                      <th className="px-4 py-2.5 text-left">Status</th>
                      <th className="px-4 py-2.5 text-center">Exc.</th>
                      <th className="px-4 py-2.5" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {phaseProcs.map(proc => {
                      const isOverdue = proc.completion_date
                        ? new Date(proc.completion_date) < new Date() && proc.status !== 'completed'
                        : false
                      return (
                        <tr
                          key={proc.id}
                          className={cn(
                            'cursor-pointer hover:bg-gray-50 transition-colors',
                            isOverdue && 'bg-red-50 hover:bg-red-50',
                            proc.exceptions_found && !isOverdue && 'bg-amber-50 hover:bg-amber-50'
                          )}
                          onClick={() => setSelectedProc(proc)}
                        >
                          <td className="px-4 py-2.5">
                            <span className="font-mono text-xs font-medium text-gray-700">{proc.seq_number}</span>
                          </td>
                          <td className="px-4 py-2.5 text-xs text-gray-500">{proc.section}</td>
                          <td className="max-w-xs px-4 py-2.5">
                            <p className="truncate text-sm font-medium text-gray-900">{proc.procedure_name}</p>
                          </td>
                          <td className="px-4 py-2.5 text-xs text-gray-500 max-w-xs">
                            <span className="truncate block">{proc.applicable_to}</span>
                          </td>
                          <td className="px-4 py-2.5">
                            <RiskBadge rating={proc.risk_rating} size="sm" />
                          </td>
                          <td className="px-4 py-2.5 text-xs text-gray-500">{proc.assigned_to ?? '—'}</td>
                          <td className="px-4 py-2.5 text-right text-xs text-gray-500">
                            {proc.budget_hours ?? '—'}/{proc.actual_hours ?? '—'}
                          </td>
                          <td className="px-4 py-2.5">
                            <StatusBadge status={proc.status} size="sm" />
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            {proc.exceptions_found && (
                              <AlertTriangle className="mx-auto h-4 w-4 text-amber-500" />
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-1">
                              {isOverdue && <Clock className="h-3.5 w-3.5 text-red-400" />}
                              <ChevronRight className="h-4 w-4 text-gray-300" />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </PhaseHeader>
            )
          })
        )}
      </div>

      {/* Drawer */}
      {selectedProc && (
        <ProcedureDrawer
          procedure={selectedProc}
          onClose={() => setSelectedProc(null)}
          onSave={handleSave}
          isSaving={updateMutation.isPending}
          teamMembers={teamMembers}
        />
      )}
    </div>
  )
}
