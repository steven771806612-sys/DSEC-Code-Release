// src/pages/reviewer/ReviewCasePage.tsx — Platform review: read AI result + submit platform review
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { get, post } from '../../lib/api'
import { PageLoader } from '../../components/ui/Loading'
import { StatusBadge, ScoreBadge } from '../../components/ui/Badge'
import { ChevronLeft, AlertCircle, CheckCircle, Info, Send } from 'lucide-react'
import type { Case, Review, CasePage } from '../../types'

interface PlatformForm {
  overall_score: number
  decision: 'approve' | 'reject' | 'revise'
  override_reason?: string
  is_override: boolean
}

export default function ReviewCasePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: c } = useQuery({ queryKey: ['case', caseId], queryFn: () => get<Case>(`/cases/${caseId}`), enabled: !!caseId })
  const { data: pages = [] } = useQuery({ queryKey: ['case-pages', caseId], queryFn: () => get<CasePage[]>(`/cases/${caseId}/pages`), enabled: !!caseId })
  const { data: reviews = [], isLoading } = useQuery({ queryKey: ['case-reviews', caseId], queryFn: () => get<Review[]>(`/cases/${caseId}/reviews`), enabled: !!caseId })

  const aiReview = reviews.find(r => r.review_type === 'ai')
  const platformReview = reviews.find(r => r.review_type === 'platform')

  const { control, register, handleSubmit } = useForm<PlatformForm>({
    defaultValues: { overall_score: aiReview?.overall_score ?? 70, decision: 'approve', is_override: false }
  })
  const overallScore = useWatch({ control, name: 'overall_score' }) ?? aiReview?.overall_score ?? 70
  const isOverride = useWatch({ control, name: 'is_override' }) ?? false

  const submitMutation = useMutation({
    mutationFn: (d: PlatformForm) => post(`/cases/${caseId}/reviews/platform`, d),
    onSuccess: () => { qc.invalidateQueries(); navigate('/reviewer') },
  })

  if (isLoading || !c) return <PageLoader />

  const canReview = c.status === 'AI_REVIEWED' && !platformReview

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="btn-ghost p-1"><ChevronLeft size={20} /></button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1>{c.title}</h1>
            <StatusBadge status={c.status} />
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{c.industry} · {c.region}</p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-5">
        {/* Left: case content */}
        <div className="col-span-3 space-y-4">
          {/* AI Review */}
          {aiReview && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-purple-700">🤖 AI 评审结果</h3>
                <div className="flex items-center gap-2">
                  <ScoreBadge score={aiReview.overall_score} />
                  <span className="text-xs text-gray-400">置信度 {((aiReview.confidence ?? 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
              {aiReview.confidence! < 0.6 && (
                <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 text-xs px-3 py-2 rounded-lg mb-3 flex items-center gap-2">
                  <AlertCircle size={13} /> AI 置信度较低，请重点人工复核
                </div>
              )}
              <div className="space-y-2">
                {aiReview.issues.slice(0, 8).map((issue, i: number) => (
                  <div key={i} className="flex gap-2 text-sm">
                    <AlertCircle size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{typeof issue === 'string' ? issue : issue.description}</span>
                  </div>
                ))}
              </div>
              {aiReview.recommendations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                  {aiReview.recommendations.slice(0, 5).map((r, i) => (
                    <div key={i} className="flex gap-2 text-sm">
                      <Info size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-600">{r}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Case pages */}
          <div className="card divide-y divide-gray-100">
            <div className="px-5 py-3 font-medium text-sm text-gray-600">案例内容</div>
            {pages.map(p => (
              <div key={p.id} className="px-5 py-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono">P{p.page_number}</span>
                  <span className="text-xs text-blue-600">{p.page_type}</span>
                  <span className="text-sm font-medium">{p.title}</span>
                </div>
                <p className="text-sm text-gray-500 line-clamp-4">{p.content_text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right: review form */}
        <div className="col-span-2">
          {platformReview ? (
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle size={18} className="text-green-600" />
                <h3 className="font-semibold">平台评审已完成</h3>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">决定</span><span className="font-medium capitalize">{platformReview.decision}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">评分</span><ScoreBadge score={platformReview.overall_score} /></div>
                <div className="flex justify-between"><span className="text-gray-500">是否覆写</span><span>{platformReview.is_override ? '是' : '否'}</span></div>
                {platformReview.override_reason && <p className="text-gray-600 bg-gray-50 rounded p-2 mt-2">{platformReview.override_reason}</p>}
              </div>
            </div>
          ) : canReview ? (
            <div className="card p-5 sticky top-4">
              <h3 className="font-semibold mb-4">提交平台评审</h3>
              <form onSubmit={handleSubmit((d) => submitMutation.mutate(d))} className="space-y-4">
                <div>
                  <label className="label">综合评分</label>
                  <div className="flex items-center gap-3">
                    <input type="range" min={0} max={100} {...register('overall_score', { valueAsNumber: true })} className="flex-1" />
                    <span className="text-lg font-bold text-brand-600 w-10 text-right">{overallScore}</span>
                  </div>
                </div>
                <div>
                  <label className="label">评审决定</label>
                  <select {...register('decision')} className="input">
                    <option value="approve">通过 — 转 DJI 终审</option>
                    <option value="revise">需修改 — 转 DJI 终审</option>
                    <option value="reject">驳回 — 退回草稿</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <input type="checkbox" {...register('is_override')} id="override" className="rounded" />
                  <label htmlFor="override" className="text-sm text-gray-700">覆写 AI 评分（需填写原因）</label>
                </div>
                {isOverride && (
                  <div>
                    <label className="label">覆写原因（必填）</label>
                    <textarea {...register('override_reason')} rows={3} className="input resize-none" placeholder="说明为何与 AI 结论不同…" />
                  </div>
                )}
                <button type="submit" className="btn-primary w-full" disabled={submitMutation.isPending}>
                  <Send size={14} /> 提交平台评审
                </button>
              </form>
            </div>
          ) : (
            <div className="card p-5 text-center text-sm text-gray-500">
              当前状态不支持平台评审操作
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
