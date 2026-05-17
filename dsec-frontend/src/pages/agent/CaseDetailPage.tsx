// src/pages/agent/CaseDetailPage.tsx — read-only case view with review results
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { get } from '../../lib/api'
import { PageLoader } from '../../components/ui/Loading'
import { StatusBadge, ScoreBadge } from '../../components/ui/Badge'
import { formatDate } from '../../lib/utils'
import { ChevronLeft, AlertCircle, CheckCircle, Info } from 'lucide-react'
import type { Case, CasePage, Review } from '../../types'

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()

  const { data: c, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => get<Case>(`/cases/${caseId}`),
    enabled: !!caseId,
  })
  const { data: pages = [] } = useQuery({
    queryKey: ['case-pages', caseId],
    queryFn: () => get<CasePage[]>(`/cases/${caseId}/pages`),
    enabled: !!caseId,
  })
  const { data: reviews = [] } = useQuery({
    queryKey: ['case-reviews', caseId],
    queryFn: () => get<Review[]>(`/cases/${caseId}/reviews`),
    enabled: !!caseId,
  })

  if (isLoading) return <PageLoader />
  if (!c) return null

  const aiReview = reviews.find(r => r.review_type === 'ai')
  const djiReview = reviews.find(r => r.review_type === 'dji')

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="btn-ghost p-1"><ChevronLeft size={20} /></button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1>{c.title}</h1>
            <StatusBadge status={c.status} />
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{c.industry} · {c.region} · {formatDate(c.updated_at)}</p>
        </div>
      </div>

      {/* AI Review summary */}
      {aiReview && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">AI 评审结果</h3>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">综合得分</span>
              <ScoreBadge score={aiReview.overall_score} />
              <span className="text-xs text-gray-400">置信度 {((aiReview.confidence ?? 0) * 100).toFixed(0)}%</span>
            </div>
          </div>

          {/* Issues */}
          {aiReview.issues.length > 0 && (
            <div className="space-y-2 mb-4">
              <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">发现问题</p>
              {aiReview.issues.slice(0, 5).map((issue, i) => (
                <div key={i} className="flex gap-2 text-sm">
                  <AlertCircle size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-700">{typeof issue === 'string' ? issue : issue.description}</span>
                </div>
              ))}
            </div>
          )}

          {/* Recommendations */}
          {aiReview.recommendations.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">改进建议</p>
              {aiReview.recommendations.slice(0, 5).map((r, i) => (
                <div key={i} className="flex gap-2 text-sm">
                  <Info size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
                  <span className="text-gray-700">{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* DJI final review */}
      {djiReview && (
        <div className={`card p-5 border-l-4 ${djiReview.decision === 'approve' ? 'border-green-500' : 'border-red-500'}`}>
          <div className="flex items-center gap-3 mb-3">
            {djiReview.decision === 'approve'
              ? <CheckCircle size={20} className="text-green-600" />
              : <AlertCircle size={20} className="text-red-600" />}
            <h3 className="font-semibold">DJI 终审结果：{djiReview.decision === 'approve' ? '通过' : '拒绝'}</h3>
            <ScoreBadge score={djiReview.overall_score} />
          </div>
          {djiReview.override_reason && (
            <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">{djiReview.override_reason}</p>
          )}
        </div>
      )}

      {/* Pages list */}
      <div className="card divide-y divide-gray-100">
        <div className="px-5 py-3 text-sm font-medium text-gray-600">案例页面 ({pages.length})</div>
        {pages.map(p => (
          <div key={p.id} className="px-5 py-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">P{p.page_number}</span>
              <span className="text-xs text-blue-600">{p.page_type}</span>
              <span className="text-sm font-medium">{p.title}</span>
            </div>
            {p.content_text && (
              <p className="text-sm text-gray-500 line-clamp-3 mt-1">{p.content_text}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
