import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md'
  className?: string
}

const STATUS_MAP: Record<string, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  in_progress: { label: 'In Progress', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  completed: { label: 'Completed', className: 'bg-green-100 text-green-700 border-green-200' },
  not_reviewed: { label: 'Not Reviewed', className: 'bg-gray-100 text-gray-500 border-gray-200' },
  in_review: { label: 'In Review', className: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
  approved: { label: 'Approved', className: 'bg-green-100 text-green-700 border-green-200' },
  open: { label: 'Open', className: 'bg-red-100 text-red-700 border-red-200' },
  partially_open: { label: 'Partially Open', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  resolved: { label: 'Resolved', className: 'bg-green-100 text-green-700 border-green-200' },
  caro_adverse: { label: 'CARO Adverse', className: 'bg-purple-100 text-purple-700 border-purple-200' },
  uploaded: { label: 'Uploaded', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  normalizing: { label: 'Normalizing', className: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
  running: { label: 'Running', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-700 border-red-200' },
  requested: { label: 'Requested', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  received: { label: 'Received', className: 'bg-green-100 text-green-700 border-green-200' },
  draft: { label: 'Draft', className: 'bg-gray-100 text-gray-600 border-gray-200' },
  final: { label: 'Final', className: 'bg-green-100 text-green-700 border-green-200' },
  reviewed: { label: 'Reviewed', className: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
}

export function StatusBadge({ status, size = 'md', className }: StatusBadgeProps) {
  const config = STATUS_MAP[status] ?? { label: status, className: 'bg-gray-100 text-gray-600 border-gray-200' }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  )
}
