// src/pages/ops/OpsDashboardPage.tsx — Admin: system metrics dashboard
import { useQuery } from '@tanstack/react-query'
import { get } from '../../lib/api'
import { PageLoader } from '../../components/ui/Loading'
import type { DashboardMetrics } from '../../types'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { TrendingUp, Database, AlertTriangle, Clock } from 'lucide-react'

const STATUS_COLORS: Record<string, string> = {
  DRAFT: '#9ca3af', SUBMITTED: '#3b82f6', AI_REVIEWED: '#8b5cf6',
  PLATFORM_REVIEWED: '#f59e0b', DJI_REVIEWED: '#f97316',
  APPROVED: '#10b981', REJECTED: '#ef4444',
}

const STATUS_LABELS: Record<string, string> = {
  DRAFT: '草稿', SUBMITTED: '已提交', AI_REVIEWED: 'AI评审',
  PLATFORM_REVIEWED: '平台评审', DJI_REVIEWED: 'DJI评审',
  APPROVED: '已通过', REJECTED: '已拒绝',
}

interface MetricCardProps {
  icon: typeof TrendingUp
  label: string
  value: string | number
  sub?: string
  color?: string
}

function MetricCard({ icon: Icon, label, value, sub, color = 'text-brand-600' }: MetricCardProps) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
          {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
        </div>
        <div className="p-2 bg-gray-100 rounded-lg">
          <Icon size={20} className="text-gray-500" />
        </div>
      </div>
    </div>
  )
}

export default function OpsDashboardPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['ops-dashboard'],
    queryFn: () => get<DashboardMetrics>('/ops/dashboard'),
    refetchInterval: 30_000,
  })

  if (isLoading) return <PageLoader />
  if (!metrics) return null

  const pieData = Object.entries(metrics.cases_by_status).map(([k, v]) => ({
    name: STATUS_LABELS[k] ?? k, value: v, color: STATUS_COLORS[k] ?? '#9ca3af'
  }))

  const vectorData = Object.entries(metrics.total_vectors).map(([k, v]) => ({
    name: k.replace('_vectors', ''), value: v
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1>系统概览</h1>
        <p className="text-sm text-gray-500 mt-1">实时监控 DSEC AI 评审平台运行状态</p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard icon={TrendingUp} label="总案例数" value={metrics.total_cases} />
        <MetricCard
          icon={TrendingUp} label="AI 评审通过率"
          value={`${metrics.ai_approval_rate.toFixed(1)}%`}
          color={metrics.ai_approval_rate >= 60 ? 'text-green-600' : 'text-red-600'}
          sub={metrics.ai_approval_rate < 60 ? '⚠️ 低于告警阈值 60%' : '正常'}
        />
        <MetricCard
          icon={AlertTriangle} label="主要分歧率"
          value={`${metrics.major_disagreement_rate.toFixed(1)}%`}
          color={metrics.major_disagreement_rate > 15 ? 'text-red-600' : 'text-green-600'}
          sub={metrics.major_disagreement_rate > 15 ? '⚠️ 超出告警阈值 15%' : '正常'}
        />
        <MetricCard
          icon={Clock} label="平均评审延迟"
          value={`${metrics.avg_review_latency_seconds.toFixed(1)}s`}
          sub="AI 评审耗时"
        />
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Case status distribution */}
        <div className="card p-5">
          <h3 className="font-semibold mb-4">案例状态分布</h3>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="50%" height={180}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                  {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip formatter={(v) => [v, '案例数']} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-1.5">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                    <span className="text-gray-600">{d.name}</span>
                  </div>
                  <span className="font-medium">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Vector DB stats */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Database size={16} className="text-gray-500" />
            <h3 className="font-semibold">向量知识库规模</h3>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={vectorData} margin={{ left: -10 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
