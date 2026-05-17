// src/pages/ops/OpsAuditPage.tsx — Audit log viewer
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { get } from '../../lib/api'
import { PageLoader, EmptyState } from '../../components/ui/Loading'
import { formatDate } from '../../lib/utils'
import { CheckCircle, XCircle } from 'lucide-react'
import type { PaginatedData } from '../../types'

interface AuditEntry {
  id: string; action: string; actor_role?: string
  resource_type?: string; timestamp: string; result: string
}

export default function OpsAuditPage() {
  const [page, setPage] = useState(1)
  const [resourceType, setResourceType] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, resourceType],
    queryFn: () => get<PaginatedData<AuditEntry>>('/ops/audit-logs', {
      page, page_size: 50, resource_type: resourceType || undefined
    }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1>审计日志</h1>
          <p className="text-sm text-gray-500 mt-1">所有用户操作与系统事件的完整记录</p>
        </div>
        <select value={resourceType} onChange={e => { setResourceType(e.target.value); setPage(1) }} className="input w-36 text-sm">
          <option value="">全部类型</option>
          {['case', 'review', 'user', 'rubric', 'prompt'].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {isLoading ? <PageLoader /> : !data?.items.length ? (
        <EmptyState title="暂无日志" />
      ) : (
        <>
          <div className="card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-5 py-3 text-xs font-medium text-gray-500 uppercase">时间</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-gray-500 uppercase">操作</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-gray-500 uppercase">角色</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-gray-500 uppercase">资源类型</th>
                  <th className="text-left px-5 py-3 text-xs font-medium text-gray-500 uppercase">结果</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.items.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 text-xs text-gray-400 whitespace-nowrap">{formatDate(log.timestamp)}</td>
                    <td className="px-5 py-3 font-mono text-xs text-gray-700">{log.action}</td>
                    <td className="px-5 py-3 text-xs text-gray-500">{log.actor_role ?? '—'}</td>
                    <td className="px-5 py-3">
                      {log.resource_type && (
                        <span className="badge bg-gray-100 text-gray-600">{log.resource_type}</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {log.result === 'success'
                        ? <CheckCircle size={14} className="text-green-500" />
                        : <XCircle size={14} className="text-red-500" />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.total > 50 && (
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
