import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Download, AlertTriangle, X } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useEngagementStore } from '@/stores/engagement.store'
import { getExceptions, createException, updateException, exportExceptions } from '@/api/exceptions'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { RiskBadge } from '@/components/shared/RiskBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { formatDate, formatCrore } from '@/lib/utils'
import type { AuditException, ExceptionStatus, RiskRating } from '@/types'

const schema = z.object({
  exception_ref: z.string().min(1),
  cap_seq: z.string().min(1),
  nature: z.string().min(1),
  description: z.string().min(10),
  account_or_lan: z.string().optional(),
  amount_crore: z.number().optional(),
  risk_rating: z.enum(['high', 'medium', 'low']),
  wp_reference: z.string().min(1),
  status: z.enum(['open', 'partially_open', 'resolved', 'caro_adverse']),
  management_response: z.string().optional(),
  suam_ref: z.string().optional(),
})

type FormData = z.infer<typeof schema>

const NATURES = ['Credit Risk', 'NPA Classification', 'ECL Provisioning', 'KYC Non-Compliance', 'RPT Disclosure', 'Income Recognition', 'Control Deficiency', 'Data Quality', 'Regulatory Non-Compliance', 'Other']

export default function Exceptions() {
  const { currentEngagementId } = useEngagementStore()
  const queryClient = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterRisk, setFilterRisk] = useState('all')

  const { data: exceptions = [], isLoading } = useQuery({
    queryKey: ['exceptions', currentEngagementId],
    queryFn: () => getExceptions(currentEngagementId!),
    enabled: !!currentEngagementId,
  })

  const createMutation = useMutation({
    mutationFn: (data: Omit<AuditException, 'id' | 'engagement_id' | 'created_at'>) =>
      createException(currentEngagementId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exceptions', currentEngagementId] })
      setShowModal(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AuditException> }) =>
      updateException(currentEngagementId!, id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['exceptions', currentEngagementId] }),
  })

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { risk_rating: 'high', status: 'open' },
  })

  const onSubmit = (data: FormData) => {
    createMutation.mutate(data as Omit<AuditException, 'id' | 'engagement_id' | 'created_at'>)
    reset()
  }

  const handleExport = async () => {
    if (!currentEngagementId) return
    const blob = await exportExceptions(currentEngagementId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'exceptions.csv'
    a.click()
  }

  const filtered = exceptions.filter(e => {
    if (filterStatus !== 'all' && e.status !== filterStatus) return false
    if (filterRisk !== 'all' && e.risk_rating !== filterRisk) return false
    return true
  })

  const stats = {
    total: exceptions.length,
    open: exceptions.filter(e => e.status === 'open').length,
    high: exceptions.filter(e => e.risk_rating === 'high').length,
    totalAmount: exceptions.reduce((s, e) => s + (e.amount_crore ?? 0), 0),
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1>Exception Register</h1>
          <p className="text-sm text-gray-500">Track all audit exceptions and management responses</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleExport} className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50">
            <Download className="h-4 w-4" />
            Export CSV
          </button>
          <button onClick={() => setShowModal(true)} className="flex items-center gap-2 rounded-lg bg-primary-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-600">
            <Plus className="h-4 w-4" />
            New Exception
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Exceptions', value: stats.total, color: 'text-gray-900' },
          { label: 'Open', value: stats.open, color: 'text-red-600' },
          { label: 'High Risk', value: stats.high, color: 'text-orange-600' },
          { label: 'Total Amount', value: formatCrore(stats.totalAmount), color: 'text-gray-900' },
        ].map(s => (
          <div key={s.label} className="rounded-xl border bg-white p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`mt-1 text-2xl font-semibold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-primary-400"
        >
          <option value="all">All Statuses</option>
          <option value="open">Open</option>
          <option value="partially_open">Partially Open</option>
          <option value="resolved">Resolved</option>
          <option value="caro_adverse">CARO Adverse</option>
        </select>
        <select
          value={filterRisk}
          onChange={e => setFilterRisk(e.target.value)}
          className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-primary-400"
        >
          <option value="all">All Risk Ratings</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border bg-white overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading exceptions…</div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="No exceptions found"
            description="Create your first exception or adjust filters"
            action={
              <button onClick={() => setShowModal(true)} className="rounded-lg bg-primary-500 px-4 py-2 text-sm font-medium text-white hover:bg-primary-600">
                Add Exception
              </button>
            }
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs font-medium text-gray-500">
                <th className="px-4 py-3 text-left">Ref</th>
                <th className="px-4 py-3 text-left">CAP Seq</th>
                <th className="px-4 py-3 text-left">Nature</th>
                <th className="px-4 py-3 text-left">Account/LAN</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3 text-left">Risk</th>
                <th className="px-4 py-3 text-left">SUAM Ref</th>
                <th className="px-4 py-3 text-left">WP Ref</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map(ex => (
                <>
                  <tr
                    key={ex.id}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedId(expandedId === ex.id ? null : ex.id)}
                  >
                    <td className="px-4 py-2.5 font-mono text-xs font-medium text-indigo-700">{ex.exception_ref}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{ex.cap_seq}</td>
                    <td className="px-4 py-2.5 text-xs font-medium text-gray-800">{ex.nature}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">{ex.account_or_lan ?? '—'}</td>
                    <td className="px-4 py-2.5 text-right text-xs font-medium text-gray-700">
                      {ex.amount_crore ? formatCrore(ex.amount_crore) : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <RiskBadge rating={ex.risk_rating} size="sm" />
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">{ex.suam_ref ?? '—'}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{ex.wp_reference}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={ex.status} size="sm" />
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-400">{formatDate(ex.created_at)}</td>
                  </tr>
                  {expandedId === ex.id && (
                    <tr key={`${ex.id}-expanded`}>
                      <td colSpan={10} className="bg-gray-50 px-6 py-4">
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <p className="mb-2 text-xs font-semibold uppercase text-gray-400">Description</p>
                            <p className="text-sm text-gray-700">{ex.description}</p>
                          </div>
                          <div>
                            <p className="mb-2 text-xs font-semibold uppercase text-gray-400">Management Response</p>
                            {ex.management_response ? (
                              <p className="text-sm text-gray-700">{ex.management_response}</p>
                            ) : (
                              <p className="text-sm italic text-gray-400">No management response yet</p>
                            )}
                            <div className="mt-3 flex gap-2">
                              {(['open', 'partially_open', 'resolved', 'caro_adverse'] as ExceptionStatus[]).map(s => (
                                <button
                                  key={s}
                                  onClick={() => updateMutation.mutate({ id: ex.id, data: { status: s } })}
                                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                                    ex.status === s ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                  }`}
                                >
                                  {s.replace('_', ' ')}
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* New Exception Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-2xl rounded-xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2>New Exception</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Exception Ref</label>
                  <input {...register('exception_ref')} placeholder="EX-001" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100" />
                  {errors.exception_ref && <p className="mt-1 text-xs text-red-600">Required</p>}
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">CAP Sequence</label>
                  <input {...register('cap_seq')} placeholder="S.03" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100" />
                  {errors.cap_seq && <p className="mt-1 text-xs text-red-600">Required</p>}
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Nature</label>
                  <select {...register('nature')} className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400">
                    {NATURES.map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Risk Rating</label>
                  <select {...register('risk_rating')} className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400">
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Account / LAN</label>
                  <input {...register('account_or_lan')} placeholder="Optional" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Amount (Cr)</label>
                  <input {...register('amount_crore', { valueAsNumber: true })} type="number" step="0.01" placeholder="0.00" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">WP Reference</label>
                  <input {...register('wp_reference')} placeholder="WP-S.03" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400" />
                  {errors.wp_reference && <p className="mt-1 text-xs text-red-600">Required</p>}
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">SUAM Ref</label>
                  <input {...register('suam_ref')} placeholder="SUAM-001 (if applicable)" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400" />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
                <textarea {...register('description')} rows={3} placeholder="Detailed description of the exception found…" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100" />
                {errors.description && <p className="mt-1 text-xs text-red-600">Min 10 characters</p>}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Management Response</label>
                <textarea {...register('management_response')} rows={2} placeholder="Management's response (if received)" className="w-full rounded-lg border px-3 py-2 text-sm outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100" />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting || createMutation.isPending} className="rounded-lg bg-primary-500 px-4 py-2 text-sm font-medium text-white hover:bg-primary-600 disabled:opacity-60">
                  {createMutation.isPending ? 'Saving…' : 'Create Exception'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
