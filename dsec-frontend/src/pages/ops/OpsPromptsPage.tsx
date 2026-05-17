// src/pages/ops/OpsPromptsPage.tsx — Prompt version management
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { get, post, put } from '../../lib/api'
import { PageLoader } from '../../components/ui/Loading'
import { Modal } from '../../components/ui/Modal'
import { formatDate } from '../../lib/utils'
import { Plus, Play, RotateCcw, Zap } from 'lucide-react'
import type { PromptVersion } from '../../types'

interface PromptFormData {
  prompt_type: string
  version: string
  content: string
}

export default function OpsPromptsPage() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [canaryPrompt, setCanaryPrompt] = useState<PromptVersion | null>(null)

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: () => get<PromptVersion[]>('/ops/prompts'),
  })

  const { register, handleSubmit, reset } = useForm<PromptFormData>()
  const { register: regCanary, handleSubmit: handleCanary } = useForm<{ canary_percentage: number }>()

  const createMutation = useMutation({
    mutationFn: (d: PromptFormData) => post('/ops/prompts', d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prompts'] }); setCreateOpen(false); reset() },
  })
  const activateMutation = useMutation({
    mutationFn: (id: string) => put(`/ops/prompts/${id}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prompts'] }),
  })
  const canaryMutation = useMutation({
    mutationFn: ({ id, pct }: { id: string; pct: number }) => put(`/ops/prompts/${id}/canary`, { canary_percentage: pct }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prompts'] }); setCanaryPrompt(null) },
  })
  const rollbackMutation = useMutation({
    mutationFn: (id: string) => post(`/ops/prompts/${id}/rollback`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['prompts'] }),
  })

  const promptTypes = [...new Set(prompts.map(p => p.prompt_type))]

  if (isLoading) return <PageLoader />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1>Prompt 版本管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理 AI 评审所使用的 Prompt 版本</p>
        </div>
        <button className="btn-primary" onClick={() => setCreateOpen(true)}><Plus size={15} /> 新建版本</button>
      </div>

      {promptTypes.map(type => (
        <div key={type} className="mb-6">
          <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">{type}</h3>
          <div className="card divide-y divide-gray-100">
            {prompts.filter(p => p.prompt_type === type).map(p => (
              <div key={p.id} className="flex items-center gap-4 px-5 py-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-medium">{p.version}</span>
                    {p.is_active && !p.is_canary && (
                      <span className="badge bg-green-100 text-green-700">当前生产版本</span>
                    )}
                    {p.is_canary && (
                      <span className="badge bg-yellow-100 text-yellow-700">
                        Canary {p.canary_percentage}%
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5 line-clamp-1">{p.content.slice(0, 80)}…</p>
                  <p className="text-xs text-gray-400">{formatDate(p.created_at)}</p>
                </div>
                <div className="flex items-center gap-2">
                  {!p.is_active && (
                    <button className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1"
                      onClick={() => activateMutation.mutate(p.id)} disabled={activateMutation.isPending}>
                      <Play size={12} /> 激活
                    </button>
                  )}
                  <button className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1"
                    onClick={() => setCanaryPrompt(p)}>
                    <Zap size={12} /> Canary
                  </button>
                  {p.is_active && (
                    <button className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1"
                      onClick={() => { if (confirm('确认回滚？')) rollbackMutation.mutate(p.id) }}>
                      <RotateCcw size={12} /> 回滚
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="新建 Prompt 版本" size="lg">
        <form onSubmit={handleSubmit((d) => createMutation.mutate(d))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">类型</label>
              <select {...register('prompt_type')} className="input">
                <option value="system">system</option>
                <option value="evaluation">evaluation</option>
                <option value="summary">summary</option>
              </select>
            </div>
            <div>
              <label className="label">版本号</label>
              <input {...register('version')} placeholder="v1.1" className="input" />
            </div>
          </div>
          <div>
            <label className="label">Prompt 内容</label>
            <textarea {...register('content')} rows={12} className="input resize-none font-mono text-xs" placeholder="输入完整 prompt 文本…" />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" className="btn-secondary" onClick={() => setCreateOpen(false)}>取消</button>
            <button type="submit" className="btn-primary" disabled={createMutation.isPending}>创建</button>
          </div>
        </form>
      </Modal>

      {/* Canary Modal */}
      {canaryPrompt && (
        <Modal open={!!canaryPrompt} onClose={() => setCanaryPrompt(null)} title={`设置 Canary — ${canaryPrompt.version}`}>
          <form onSubmit={handleCanary((d) => canaryMutation.mutate({ id: canaryPrompt.id, pct: d.canary_percentage }))} className="space-y-4">
            <p className="text-sm text-gray-600">设置此版本接收的流量比例（0 = 禁用 Canary）</p>
            <div>
              <label className="label">流量比例 (%)</label>
              <input type="number" {...regCanary('canary_percentage', { valueAsNumber: true })} min={0} max={100} defaultValue={canaryPrompt.canary_percentage} className="input" />
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setCanaryPrompt(null)}>取消</button>
              <button type="submit" className="btn-primary" disabled={canaryMutation.isPending}>保存</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
