// src/pages/agent/CaseEditPage.tsx — Case editor: metadata + pages + submit
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { get, patch, post, put, del } from '../../lib/api'
import { PageLoader } from '../../components/ui/Loading'
import { StatusBadge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import type { Case, CasePage } from '../../types'
import { Plus, Save, Send, ChevronLeft, Trash2, FileText } from 'lucide-react'

const PAGE_TYPES = ['overview', 'architecture', 'deployment', 'results', 'appendix']
const PAGE_TYPE_LABELS: Record<string, string> = {
  overview: '项目概述', architecture: '架构设计', deployment: '部署详情', results: '效果与ROI', appendix: '附件',
}

interface PageFormData {
  page_type: string
  title?: string
  content_text?: string
}

interface PageUpdatePayload extends PageFormData {
  id: string
}

export default function CaseEditPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [addPageOpen, setAddPageOpen] = useState(false)
  const [activePage, setActivePage] = useState<CasePage | null>(null)
  const [submitOpen, setSubmitOpen] = useState(false)

  const { data: caseData, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => get<Case>(`/cases/${caseId}`),
    enabled: !!caseId,
  })

  const { data: pages = [], isLoading: pagesLoading } = useQuery({
    queryKey: ['case-pages', caseId],
    queryFn: () => get<CasePage[]>(`/cases/${caseId}/pages`),
    enabled: !!caseId,
  })

  const { register, handleSubmit } = useForm<Partial<Case>>()
  const { register: regPage, handleSubmit: handlePageSubmit, reset: resetPage } = useForm<PageFormData>()

  const saveMeta = useMutation({
    mutationFn: (d: Partial<Case>) => patch<Case>(`/cases/${caseId}`, d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['case', caseId] }),
  })

  const addPage = useMutation({
    mutationFn: (d: PageFormData) => post<CasePage>(`/cases/${caseId}/pages`, { ...d, page_number: pages.length + 1 }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['case-pages', caseId] }); setAddPageOpen(false); resetPage() },
  })

  const updatePage = useMutation({
    mutationFn: ({ id, ...d }: PageUpdatePayload) => put<CasePage>(`/cases/${caseId}/pages/${id}`, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['case-pages', caseId] }); setActivePage(null) },
  })

  const deletePage = useMutation({
    mutationFn: (id: string) => del(`/cases/${caseId}/pages/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['case-pages', caseId] }),
  })

  const submitCase = useMutation({
    mutationFn: (summary: string) => post(`/cases/${caseId}/submit`, { change_summary: summary }),
    onSuccess: () => { setSubmitOpen(false); navigate('/agent') },
  })

  if (isLoading) return <PageLoader />
  const c = caseData!
  const isEditable = c.status === 'DRAFT'

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/agent')} className="btn-ghost p-1">
          <ChevronLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">{c.title}</h1>
            <StatusBadge status={c.status} />
          </div>
          <p className="text-sm text-gray-500 mt-0.5">Rubric: {c.rubric_version}</p>
        </div>
        {isEditable && (
          <button className="btn-primary" onClick={() => setSubmitOpen(true)} disabled={!pages.length}>
            <Send size={15} /> 提交评审
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-5">
        {/* Left: meta */}
        <div className="card p-5 space-y-4">
          <h3 className="font-medium text-gray-700">基本信息</h3>
          <form onSubmit={handleSubmit((d) => saveMeta.mutate(d))} className="space-y-3">
            <div>
              <label className="label">案例标题</label>
              <input {...register('title')} defaultValue={c.title} className="input" disabled={!isEditable} />
            </div>
            <div>
              <label className="label">行业</label>
              <select {...register('industry')} defaultValue={c.industry ?? ''} className="input" disabled={!isEditable}>
                <option value="">选择行业</option>
                {['retail', 'logistics', 'manufacturing', 'finance', 'government', 'education', 'healthcare'].map(i => (
                  <option key={i} value={i}>{i}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">地区</label>
              <select {...register('region')} defaultValue={c.region ?? ''} className="input" disabled={!isEditable}>
                <option value="">选择地区</option>
                {['APAC', 'EMEA', 'AMER'].map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            {isEditable && (
              <button type="submit" className="btn-secondary w-full" disabled={saveMeta.isPending}>
                <Save size={14} /> 保存
              </button>
            )}
          </form>
        </div>

        {/* Right: pages */}
        <div className="col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-gray-700">案例页面 ({pages.length})</h3>
            {isEditable && (
              <button className="btn-secondary text-xs px-3 py-1.5" onClick={() => setAddPageOpen(true)}>
                <Plus size={13} /> 添加页面
              </button>
            )}
          </div>

          {pagesLoading ? <PageLoader /> : pages.length === 0 ? (
            <div className="card p-8 text-center">
              <FileText size={32} className="mx-auto text-gray-300 mb-3" />
              <p className="text-sm text-gray-500">请添加至少一个页面再提交</p>
            </div>
          ) : (
            <div className="space-y-3">
              {pages.map((p) => (
                <div key={p.id} className="card p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded">P{p.page_number}</span>
                        <span className="text-xs text-gray-500 bg-blue-50 px-2 py-0.5 rounded-full">
                          {PAGE_TYPE_LABELS[p.page_type ?? ''] ?? p.page_type}
                        </span>
                      </div>
                      <p className="font-medium text-sm mt-1">{p.title ?? '(无标题)'}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{p.word_count} 字</p>
                    </div>
                    {isEditable && (
                      <div className="flex gap-1">
                        <button className="btn-ghost p-1.5 text-xs" onClick={() => setActivePage(p)}>编辑</button>
                        <button
                          className="btn-ghost p-1.5 text-red-500"
                          onClick={() => { if (confirm('确认删除？')) deletePage.mutate(p.id) }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                  {p.content_text && (
                    <p className="text-xs text-gray-500 mt-2 line-clamp-2">{p.content_text}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add Page Modal */}
      <Modal open={addPageOpen} onClose={() => setAddPageOpen(false)} title="添加页面">
        <form onSubmit={handlePageSubmit((d) => addPage.mutate(d))} className="space-y-4">
          <div>
            <label className="label">页面类型</label>
            <select {...regPage('page_type')} className="input">
              {PAGE_TYPES.map(t => <option key={t} value={t}>{PAGE_TYPE_LABELS[t]}</option>)}
            </select>
          </div>
          <div>
            <label className="label">标题</label>
            <input {...regPage('title')} className="input" placeholder="例如：项目背景与业务目标" />
          </div>
          <div>
            <label className="label">内容（供 AI 评审）</label>
            <textarea {...regPage('content_text')} rows={8} className="input resize-none" placeholder="详细描述本页面内容…" />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" className="btn-secondary" onClick={() => setAddPageOpen(false)}>取消</button>
            <button type="submit" className="btn-primary" disabled={addPage.isPending}>添加</button>
          </div>
        </form>
      </Modal>

      {/* Edit Page Modal */}
      {activePage && (
        <Modal open={!!activePage} onClose={() => setActivePage(null)} title="编辑页面" size="lg">
          <form onSubmit={handlePageSubmit((d) => updatePage.mutate({ id: activePage.id, ...d }))} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">页面类型</label>
                <select {...regPage('page_type')} defaultValue={activePage.page_type ?? ''} className="input">
                  {PAGE_TYPES.map(t => <option key={t} value={t}>{PAGE_TYPE_LABELS[t]}</option>)}
                </select>
              </div>
              <div>
                <label className="label">标题</label>
                <input {...regPage('title')} defaultValue={activePage.title ?? ''} className="input" />
              </div>
            </div>
            <div>
              <label className="label">内容</label>
              <textarea {...regPage('content_text')} defaultValue={activePage.content_text ?? ''} rows={12} className="input resize-none font-mono text-sm" />
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setActivePage(null)}>取消</button>
              <button type="submit" className="btn-primary" disabled={updatePage.isPending}>保存</button>
            </div>
          </form>
        </Modal>
      )}

      {/* Submit Modal */}
      <Modal open={submitOpen} onClose={() => setSubmitOpen(false)} title="提交案例评审">
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700">
            提交后将触发 AI 自动评审，提交后 5 分钟内可撤回。
          </div>
          <div>
            <label className="label">版本说明（可选）</label>
            <textarea
              className="input resize-none"
              rows={3}
              placeholder="描述本次提交的变更内容…"
              id="submit-summary"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button className="btn-secondary" onClick={() => setSubmitOpen(false)}>取消</button>
            <button
              className="btn-primary"
              disabled={submitCase.isPending}
              onClick={() => {
                const summary = (document.getElementById('submit-summary') as HTMLTextAreaElement)?.value
                submitCase.mutate(summary)
              }}
            >
              <Send size={14} /> 确认提交
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
