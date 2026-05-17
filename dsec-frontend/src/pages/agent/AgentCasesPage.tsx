// src/pages/agent/AgentCasesPage.tsx — Agent: my cases list
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, del } from '../../lib/api'
import { StatusBadge } from '../../components/ui/Badge'
import { PageLoader, EmptyState } from '../../components/ui/Loading'
import { formatDate } from '../../lib/utils'
import { Plus, Trash2, Eye } from 'lucide-react'
import type { Case, PaginatedData } from '../../types'

export default function AgentCasesPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['my-cases', page],
    queryFn: () => get<PaginatedData<Case>>('/cases', { page, page_size: 10 }),
  })

  const createMutation = useMutation({
    mutationFn: () => post<Case>('/cases', { title: '新案例 ' + new Date().toLocaleDateString() }),
    onSuccess: (c) => navigate(`/agent/cases/${c.id}/edit`),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`/cases/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-cases'] }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1>我的案例</h1>
          <p className="text-sm text-gray-500 mt-1">管理并提交您的安防集成案例</p>
        </div>
        <button
          className="btn-primary"
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
        >
          <Plus size={16} /> 新建案例
        </button>
      </div>

      {isLoading ? <PageLoader /> : !data?.items.length ? (
        <EmptyState title="暂无案例" desc={'点击右上角"新建案例"开始创建'} />
      ) : (
        <>
          <div className="card divide-y divide-gray-100">
            {data.items.map((c) => (
              <div key={c.id} className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors">
                <div className="flex-1 min-w-0">
                  <Link to={`/agent/cases/${c.id}/edit`} className="font-medium text-gray-900 hover:text-brand-600 truncate block">
                    {c.title}
                  </Link>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>{c.industry ?? '未设行业'}</span>
                    <span>·</span>
                    <span>{formatDate(c.updated_at)}</span>
                  </div>
                </div>
                <StatusBadge status={c.status} />
                <div className="flex items-center gap-1">
                  <Link to={`/agent/cases/${c.id}`} className="btn-ghost p-2" title="查看详情">
                    <Eye size={15} />
                  </Link>
                  {c.status === 'DRAFT' && (
                    <button
                      className="btn-ghost p-2 text-red-500 hover:bg-red-50"
                      title="删除"
                      onClick={() => { if (confirm('确认删除？')) deleteMutation.mutate(c.id) }}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          {/* Pagination */}
          {data.total > 10 && (
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
