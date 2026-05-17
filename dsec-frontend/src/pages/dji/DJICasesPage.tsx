// src/pages/dji/DJICasesPage.tsx — DJI SE: all cases management
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { get } from '../../lib/api'
import { PageLoader, EmptyState } from '../../components/ui/Loading'
import { StatusBadge } from '../../components/ui/Badge'
import { formatDate } from '../../lib/utils'
import { Search } from 'lucide-react'
import type { Case, PaginatedData } from '../../types'

const STATUS_FILTERS = ['', 'SUBMITTED', 'AI_REVIEWED', 'PLATFORM_REVIEWED', 'DJI_REVIEWED', 'APPROVED', 'REJECTED']

export default function DJICasesPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['all-cases', page, status],
    queryFn: () => get<PaginatedData<Case>>('/cases', { page, page_size: 20, status: status || undefined }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1>案例管理</h1>
          <p className="text-sm text-gray-500 mt-1">全量案例查看与终审操作</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索案例…" className="input pl-9 text-sm" />
        </div>
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1) }} className="input w-44 text-sm">
          {STATUS_FILTERS.map(s => (
            <option key={s} value={s}>{s || '全部状态'}</option>
          ))}
        </select>
      </div>

      {isLoading ? <PageLoader /> : !data?.items.length ? (
        <EmptyState title="暂无案例" />
      ) : (
        <>
          <div className="card divide-y divide-gray-100">
            <div className="grid grid-cols-12 gap-4 px-5 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
              <div className="col-span-5">案例</div>
              <div className="col-span-2">状态</div>
              <div className="col-span-2">行业</div>
              <div className="col-span-2">更新时间</div>
              <div className="col-span-1"></div>
            </div>
            {data.items.map((c) => (
              <div key={c.id} className="grid grid-cols-12 gap-4 items-center px-5 py-4 hover:bg-gray-50 transition-colors">
                <div className="col-span-5 min-w-0">
                  <Link to={`/dji/cases/${c.id}`} className="font-medium text-gray-900 hover:text-brand-600 block truncate text-sm">
                    {c.title}
                  </Link>
                  <p className="text-xs text-gray-400 mt-0.5">{c.id.slice(0, 8)}…</p>
                </div>
                <div className="col-span-2"><StatusBadge status={c.status} /></div>
                <div className="col-span-2 text-sm text-gray-500">{c.industry ?? '—'}</div>
                <div className="col-span-2 text-xs text-gray-400">{formatDate(c.updated_at)}</div>
                <div className="col-span-1 flex justify-end">
                  <Link to={`/dji/cases/${c.id}`} className="btn-secondary text-xs px-3 py-1">查看</Link>
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
