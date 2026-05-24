import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn, PHASE_LABELS, PHASE_COLORS } from '@/lib/utils'
import type { Phase } from '@/types'

interface PhaseHeaderProps {
  phase: Phase
  total: number
  completed: number
  defaultOpen?: boolean
  children: React.ReactNode
}

export function PhaseHeader({ phase, total, completed, defaultOpen = true, children }: PhaseHeaderProps) {
  const [open, setOpen] = useState(defaultOpen)
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <div className="overflow-hidden rounded-lg border bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 hover:bg-gray-50"
      >
        <div className="flex items-center gap-3">
          {open ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium', PHASE_COLORS[phase])}>
            {PHASE_LABELS[phase]}
          </span>
          <span className="text-sm text-gray-600">
            {completed}/{total} completed
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-2 w-32 rounded-full bg-gray-100">
            <div
              className="h-2 rounded-full bg-primary-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="w-10 text-right text-xs font-medium text-gray-600">{pct}%</span>
        </div>
      </button>
      {open && <div className="border-t">{children}</div>}
    </div>
  )
}
