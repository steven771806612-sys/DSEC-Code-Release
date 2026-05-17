// src/pages/ops/OpsDisagreementsPage.tsx — Disagreement analysis
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post } from '../../lib/api'
import { PageLoader, EmptyState } from '../../components/ui/Loading'
import { formatDate } from '../../lib/utils'
import { AlertTriangle, Zap } from 'lucide-react'
import type { DisagreementRecord, PaginatedData } from '../../types'

const SEVERITY_STYLE: Record<string, string> = {
  minor: 'badge bg-yellow-100 text-yellow-700',
  major: 'badge bg-orange-100 text-orange-700',
  critical: 'badge bg-red-100 text-red-700',
}

export default function OpsDisagreementsPage() {
  const [page, setPage] = useState(1)
  const [severity, setSeverity] = useState('')
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['disagreements', page, severity],
    queryFn: () => get<PaginatedData<DisagreementRecord>>('/rag/disagreements', {
      page, page_size: 20, severity: severity || undefined
    }),
  })

  const markMutation = useMutation({
    mutationFn: (id: string) => post(`/rag/disagreements/${id}/mark-training-signal`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['disagreements'] }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1>分歧分析</h1>
          <p className="text-sm text-gray-500 mt-1">AI 评审与人工评审的分歧记录</p>
        </div>
        <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1) }} className="input w-36 text-sm">
          <option value="">全部严重度</option>
          <option value="minor">Minor</option>
          <option value="major">Major</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {isLoading ? <PageLoader /> : !data?.items.length ? (
        <EmptyState title="暂无分歧记录" desc="AI 与人工评审分歧超阈值时自动记录" />
      ) : (
        <>
          <div className="card divide-y divide-gray-100">
            {data.items.map((r) => (
              <div key={r.id} className="px-5 py-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={16} className="text-orange-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={SEVERITY_STYLE[r.severity ?? 'minor'] ?? 'badge'}>{r.severity}</span>
                        <span className="text-sm font-medium">{r.disagreement_type?.replace('_', ' ')}</span>
                        {r.dimension && <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">{r.dimension}</span>}
                        {r.is_training_signal && (
                          <span className="badge bg-purple-100 text-purple-700 flex items-center gap-1">
                            <Zap size={10} /> 训练信号
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-sm text-gray-600">
                        <span>AI: <strong>{r.ai_score?.toFixed(1) ?? '—'}</strong></span>
                        <span>人工: <strong>{r.human_score?.toFixed(1) ?? '—'}</strong></span>
                        <span className="text-red-600">差距: <strong>{r.score_gap?.toFixed(1) ?? '—'}</strong></span>
                      </div>
                      <p className="text-xs text-gray-400 mt-1">{formatDate(r.created_at)}</p>
                    </div>
                  </div>
                  {!r.is_training_signal && (
                    <button
                      className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1 flex-shrink-0"
                      onClick={() => markMutation.mutate(r.id)}
                      disabled={markMutation.isPending}
                    >
                      <Zap size={12} /> 标记训练信号
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          {data.total > 20 && (
            <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
              <span>共 {data.total} 条</span>
              <div className="flex gap-2">
                <button className="btn-secondary px-3 py-1 text-xs" disabled={page === 1} onClick={() => setPage(p => p - 1)}>上一页</button>
                <button className="btn-secondary px-3 py-1 text-xs" disabled={!data.has_next} onClick={() => setPage(p => p + 1)}>下一页</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
