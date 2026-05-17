// src/App.tsx — root router
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProtectedRoute } from './router/ProtectedRoute'
import { useAuthStore } from './store/authStore'

// Auth
import LoginPage from './pages/auth/LoginPage'

// Agent
import AgentCasesPage from './pages/agent/AgentCasesPage'
import CaseEditPage from './pages/agent/CaseEditPage'
import CaseDetailPage from './pages/agent/CaseDetailPage'

// Reviewer
import ReviewerTasksPage from './pages/reviewer/ReviewerTasksPage'
import ReviewCasePage from './pages/reviewer/ReviewCasePage'

// DJI SE
import DJICasesPage from './pages/dji/DJICasesPage'
import DJIReviewPage from './pages/dji/DJIReviewPage'

// Ops
import OpsDashboardPage from './pages/ops/OpsDashboardPage'
import OpsPromptsPage from './pages/ops/OpsPromptsPage'
import OpsDisagreementsPage from './pages/ops/OpsDisagreementsPage'
import OpsAuditPage from './pages/ops/OpsAuditPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

function RootRedirect() {
  const { user } = useAuthStore()
  const roleRedirect: Record<string, string> = {
    agent: '/agent', platform_reviewer: '/reviewer',
    dji_se: '/dji', admin: '/ops/dashboard',
  }
  return <Navigate to={user ? (roleRedirect[user.role] ?? '/login') : '/login'} replace />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<RootRedirect />} />

          {/* Agent */}
          <Route path="/agent" element={<ProtectedRoute roles={['agent', 'admin']}><AgentCasesPage /></ProtectedRoute>} />
          <Route path="/agent/cases/:caseId/edit" element={<ProtectedRoute roles={['agent', 'admin']}><CaseEditPage /></ProtectedRoute>} />
          <Route path="/agent/cases/:caseId" element={<ProtectedRoute roles={['agent', 'admin']}><CaseDetailPage /></ProtectedRoute>} />

          {/* Reviewer */}
          <Route path="/reviewer" element={<ProtectedRoute roles={['platform_reviewer', 'admin']}><ReviewerTasksPage /></ProtectedRoute>} />
          <Route path="/reviewer/cases" element={<ProtectedRoute roles={['platform_reviewer', 'admin']}><DJICasesPage /></ProtectedRoute>} />
          <Route path="/reviewer/cases/:caseId" element={<ProtectedRoute roles={['platform_reviewer', 'admin']}><ReviewCasePage /></ProtectedRoute>} />

          {/* DJI SE */}
          <Route path="/dji" element={<ProtectedRoute roles={['dji_se', 'admin']}><DJICasesPage /></ProtectedRoute>} />
          <Route path="/dji/cases/:caseId" element={<ProtectedRoute roles={['dji_se', 'admin']}><DJIReviewPage /></ProtectedRoute>} />
          <Route path="/dji/disagreements" element={<ProtectedRoute roles={['dji_se', 'admin']}><OpsDisagreementsPage /></ProtectedRoute>} />

          {/* Ops */}
          <Route path="/ops/dashboard" element={<ProtectedRoute roles={['admin']}><OpsDashboardPage /></ProtectedRoute>} />
          <Route path="/ops/cases" element={<ProtectedRoute roles={['admin']}><DJICasesPage /></ProtectedRoute>} />
          <Route path="/ops/prompts" element={<ProtectedRoute roles={['admin']}><OpsPromptsPage /></ProtectedRoute>} />
          <Route path="/ops/disagreements" element={<ProtectedRoute roles={['admin']}><OpsDisagreementsPage /></ProtectedRoute>} />
          <Route path="/ops/audit" element={<ProtectedRoute roles={['admin']}><OpsAuditPage /></ProtectedRoute>} />

          {/* Fallback */}
          <Route path="/unauthorized" element={<div className="flex h-screen items-center justify-center text-gray-500">无权访问此页面</div>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
