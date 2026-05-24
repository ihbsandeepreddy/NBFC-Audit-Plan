import { cn } from '@/lib/utils'
import type { RiskRating } from '@/types'

interface RiskBadgeProps {
  rating: RiskRating | string
  size?: 'sm' | 'md'
  className?: string
}

const RISK_MAP: Record<string, { label: string; className: string }> = {
  high: { label: 'High', className: 'bg-red-100 text-red-700 border-red-200' },
  medium: { label: 'Medium', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  low: { label: 'Low', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  Critical: { label: 'Critical', className: 'bg-red-200 text-red-800 border-red-300' },
  High: { label: 'High', className: 'bg-red-100 text-red-700 border-red-200' },
  Medium: { label: 'Medium', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  Low: { label: 'Low', className: 'bg-blue-100 text-blue-700 border-blue-200' },
}

export function RiskBadge({ rating, size = 'md', className }: RiskBadgeProps) {
  const config = RISK_MAP[rating] ?? { label: rating, className: 'bg-gray-100 text-gray-600 border-gray-200' }

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
