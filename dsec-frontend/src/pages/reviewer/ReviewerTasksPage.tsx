// src/pages/reviewer/ReviewerTasksPage.tsx — Platform reviewer task list
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { get } from '../../lib/api'
import { PageLoader, EmptyState } from '../../components/ui/Loading'
import { formatDate } from '../../lib/utils'
import { AlertTriangle, Clock } from 'lucide-react'
import type { ReviewTask, PaginatedData } from '../../types'

export default function ReviewerTasksPage() {
  const [page] = useState(1)
  const { data, isLoading } = useQuery({
    queryKey: ['my-tasks', page],
    queryFn: () => get<PaginatedData<ReviewTask>>('/reviews/tasks', { page, page_size: 20 }),
  })

  if (isLoading) return <PageLoader />

  return (
    <div>
      <div className="mb-6">
        <h1>评审任务</h1>
        <p className="text-sm text-gray-500 mt-1">待处理的平台评审任务</p>
      </div>

      {!data?.items.length ? (
        <EmptyState title="暂无评审任务" desc="当前没有需要处理的任务" />
      ) : (
        <div className="card divide-y divide-gray-100">
          {data.items.map((task) => (
            <Link
              key={task.id}
              to={`/reviewer/cases/${task.case_id}`}
              className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">案例 {task.case_id.slice(0, 8)}…</span>
                  {task.sla_breached && (
                    <span className="flex items-center gap-1 text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                      <AlertTriangle size={11} /> SLA 超时
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                  <span className="capitalize">{task.review_type} 评审</span>
                  {task.due_at && (
                    <span className="flex items-center gap-1">
                      <Clock size={11} /> 截止 {formatDate(task.due_at)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`badge ${task.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                  {task.status === 'pending' ? '待处理' : '进行中'}
                </span>
                <span className="text-xs text-gray-400">优先级 {task.priority}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
