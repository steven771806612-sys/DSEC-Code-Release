// src/components/ui/Badge.tsx
import { cn, statusBadgeClass, statusLabel } from '../../lib/utils'

interface BadgeProps {
  status: string
  className?: string
}

export function StatusBadge({ status, className }: BadgeProps) {
  return (
    <span className={cn(statusBadgeClass(status), className)}>
      {statusLabel(status)}
    </span>
  )
}

interface ScoreBadgeProps { score?: number | null }
export function ScoreBadge({ score }: ScoreBadgeProps) {
  if (score == null) return <span className="badge bg-gray-100 text-gray-500">—</span>
  const color = score >= 75 ? 'bg-green-100 text-green-700' : score >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
  return <span className={`badge ${color}`}>{score.toFixed(1)}</span>
}
