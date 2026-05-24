import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCrore(val: number | null | undefined): string {
  if (val == null) return '—'
  return `₹${val.toLocaleString('en-IN', { maximumFractionDigits: 2 })} Cr`
}

export function formatPct(val: number | null | undefined): string {
  if (val == null) return '—'
  return `${val.toFixed(2)}%`
}

export function formatDate(val: string | null | undefined): string {
  if (!val) return '—'
  try {
    return new Date(val).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return val
  }
}

export function daysUntil(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null
  const diff = new Date(dateStr).getTime() - Date.now()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

export const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-amber-100 text-amber-700',
  completed: 'bg-green-100 text-green-700',
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-blue-100 text-blue-700',
  not_reviewed: 'bg-gray-100 text-gray-500',
  in_review: 'bg-indigo-100 text-indigo-700',
  approved: 'bg-green-100 text-green-700',
  open: 'bg-red-100 text-red-700',
  partially_open: 'bg-amber-100 text-amber-700',
  resolved: 'bg-green-100 text-green-700',
  caro_adverse: 'bg-purple-100 text-purple-700',
}

export const PHASE_LABELS: Record<string, string> = {
  planning: 'Planning',
  risk_assessment: 'Risk Assessment',
  controls: 'Controls',
  substantive: 'Substantive',
  completion: 'Completion',
}

export const PHASE_COLORS: Record<string, string> = {
  planning: 'bg-violet-100 text-violet-700',
  risk_assessment: 'bg-blue-100 text-blue-700',
  controls: 'bg-cyan-100 text-cyan-700',
  substantive: 'bg-amber-100 text-amber-700',
  completion: 'bg-green-100 text-green-700',
}
