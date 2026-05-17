// src/pages/dji/DJIReviewPage.tsx — DJI SE: full review chain + final decision
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { get, post } from '../../lib/api'
import { PageLoader } from '../../components/ui/Loading'
import { StatusBadge, ScoreBadge } from '../../components/ui/Badge'
import { ChevronLeft, CheckCircle, XCircle, AlertCircle, Bot, User, Shield } from 'lucide-react'
import type { Case, Review, CasePage } from '../../types'

interface DJIForm { overall_score: number; decision: 'approve' | 'reject'; override_reason?: string }

const reviewTypeIcon = { ai: <Bot size={15} className="text-purple-600" />, platform: <User size={15} className="text-blue-600" />, dji: <Shield size={15} className="text-orange-600" /> }
const reviewTypeLabel = { ai: 'AI 评审', platform: '平台评审', dji: 'DJI 终审' }

export default function DJIReviewPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: c } = useQuery({ queryKey: ['case', caseId], queryFn: () => get<Case>(`/cases/${caseId}`), enabled: !!caseId })
  const { data: pages = [] } = useQuery({ queryKey: ['case-pages', caseId], queryFn: () => get<CasePage[]>(`/cases/${caseId}/pages`), enabled: !!caseId })
  const { data: reviews = [], isLoading } = useQuery({ queryKey: ['case-reviews', caseId], queryFn: () => get<Review[]>(`/cases/${caseId}/reviews`), enabled: !!caseId })

  const { control, register, handleSubmit } = useForm<DJIForm>({ defaultValues: { overall_score: 75, decision: 'approve' } })
  const overallScore = useWatch({ control, name: 'overall_score' }) ?? 75
  const decision = useWatch({ control, name: 'decision' }) ?? 'approve'

  const submitMutation = useMutation({
    mutationFn: (d: DJIForm) => post(`/cases/${caseId}/reviews/dji`, d),
    onSuccess: () => { qc.invalidateQueries(); navigate('/dji') },
  })

  if (isLoading || !c) return <PageLoader />

  const djiReview = reviews.find(r => r.review_type === 'dji')
  const canReview = c.status === 'PLATFORM_REVIEWED' && !djiReview

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="btn-ghost p-1"><ChevronLeft size={20} /></button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1>{c.title}</h1>
            <StatusBadge status={c.status} />
          </div>
          <p className="text-sm text-gray-500">{c.industry} · {c.region} · Rubric {c.rubric_version}</p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-5">
        {/* Left: full review chain */}
        <div className="col-span-3 space-y-4">
          {/* Review timeline */}
          {reviews.map((r) => (
            <div key={r.id} className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {reviewTypeIcon[r.review_type as keyof typeof reviewTypeIcon]}
                  <span className="font-medium text-sm">{reviewTypeLabel[r.review_type as keyof typeof reviewTypeLabel]}</span>
                  {r.is_override && <span className="badge bg-orange-100 text-orange-700">已覆写</span>}
                </div>
                <div className="flex items-center gap-2">
                  <ScoreBadge score={r.overall_score} />
                  {r.confidence && <span className="text-xs text-gray-400">置信度 {(r.confidence * 100).toFixed(0)}%</span>}
                </div>
              </div>
              {r.issues.length > 0 && (
                <div className="space-y-1.5 mb-3">
                  {r.issues.slice(0, 5).map((issue, i: number) => (
                    <div key={i} className="flex gap-2 text-sm text-gray-600">
                      <AlertCircle size={13} className="text-red-400 mt-0.5 flex-shrink-0" />
                      {typeof issue === 'string' ? issue : issue.description}
                    </div>
                  ))}
                </div>
              )}
              {r.override_reason && (
                <div className="bg-orange-50 border border-orange-100 rounded-lg p-3 text-sm text-orange-800">
                  覆写说明：{r.override_reason}
                </div>
              )}
            </div>
          ))}

          {/* Case pages */}
          <div className="card divide-y divide-gray-100">
            <div className="px-5 py-3 text-sm font-medium text-gray-600">案例内容</div>
            {pages.map(p => (
              <div key={p.id} className="px-5 py-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">P{p.page_number}</span>
                  <span className="text-xs text-blue-600">{p.page_type}</span>
                  <span className="text-sm font-medium">{p.title}</span>
                  <span className="text-xs text-gray-400 ml-auto">{p.word_count} 字</span>
                </div>
                <p className="text-sm text-gray-500">{p.content_text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right: DJI decision form */}
        <div className="col-span-2">
          {djiReview ? (
            <div className={`card p-5 border-t-4 ${djiReview.decision === 'approve' ? 'border-green-500' : 'border-red-500'}`}>
              <div className="flex items-center gap-2 mb-4">
                {djiReview.decision === 'approve'
                  ? <CheckCircle size={20} className="text-green-600" />
                  : <XCircle size={20} className="text-red-600" />}
                <h3 className="font-semibold">终审已完成</h3>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">决定</span>
                  <span className={`font-bold ${djiReview.decision === 'approve' ? 'text-green-600' : 'text-red-600'}`}>
                    {djiReview.decision === 'approve' ? '通过' : '拒绝'}
                  </span>
                </div>
                <div className="flex justify-between"><span className="text-gray-500">最终评分</span><ScoreBadge score={djiReview.overall_score} /></div>
              </div>
            </div>
          ) : canReview ? (
            <div className="card p-5 sticky top-4">
              <h3 className="font-semibold mb-1">DJI 终审决定</h3>
              <p className="text-xs text-gray-500 mb-4">此决定为最终裁定，将自动录入知识库</p>
              <form onSubmit={handleSubmit((d) => submitMutation.mutate(d))} className="space-y-4">
                <div>
                  <label className="label">最终评分</label>
                  <div className="flex items-center gap-3">
                    <input type="range" min={0} max={100} {...register('overall_score', { valueAsNumber: true })} className="flex-1" />
                    <span className="text-2xl font-bold text-brand-600 w-12 text-right">{overallScore}</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <label className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 cursor-pointer transition-all ${decision === 'approve' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-gray-300'}`}>
                    <input type="radio" {...register('decision')} value="approve" className="sr-only" />
                    <CheckCircle size={24} className={decision === 'approve' ? 'text-green-600' : 'text-gray-400'} />
                    <span className="text-sm font-medium">通过</span>
                  </label>
                  <label className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 cursor-pointer transition-all ${decision === 'reject' ? 'border-red-500 bg-red-50' : 'border-gray-200 hover:border-gray-300'}`}>
                    <input type="radio" {...register('decision')} value="reject" className="sr-only" />
                    <XCircle size={24} className={decision === 'reject' ? 'text-red-600' : 'text-gray-400'} />
                    <span className="text-sm font-medium">拒绝</span>
                  </label>
                </div>
                <div>
                  <label className="label">终审意见（可选）</label>
                  <textarea {...register('override_reason')} rows={4} className="input resize-none" placeholder="填写详细评审意见，将发送给代理商…" />
                </div>
                <button type="submit" className={`w-full btn ${decision === 'approve' ? 'btn-primary' : 'btn-danger'}`} disabled={submitMutation.isPending}>
                  {decision === 'approve' ? <CheckCircle size={15} /> : <XCircle size={15} />}
                  确认{decision === 'approve' ? '通过' : '拒绝'}
                </button>
              </form>
            </div>
          ) : (
            <div className="card p-5 text-center text-sm text-gray-500">
              当前状态：{c.status}，暂不支持终审操作
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
